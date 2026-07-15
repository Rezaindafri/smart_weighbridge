import cv2
import torch
import re 
import time
from ultralytics import YOLO
from paddleocr import PaddleOCR
from pymodbus.client import ModbusTcpClient # Library untuk komunikasi ke OpenPLC

torch.backends.cudnn.enabled = False
print("[INFO] PyTorch cuDNN dinonaktifkan agar tidak bentrok dengan PaddleOCR.")

# ==========================================
# KONFIGURASI KAMERA
# ==========================================
CAMERA_SOURCE = 0 
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

def open_video_capture(source):
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    return cap

def koreksi_plat_indo(teks):
    num_to_char = {'8': 'B', '0': 'O', '1': 'I', '5': 'S', '4': 'A', '2': 'Z', '6': 'G'}
    teks = re.sub(r'[^A-Z0-9]', '', teks.upper())
    
    if len(teks) < 4:
        return teks
        
    teks_list = list(teks)
    
    if teks_list[0] in num_to_char:
        teks_list[0] = num_to_char[teks_list[0]]
        
    if len(teks_list) >= 3 and teks_list[1].isdigit() and teks_list[2].isalpha():
        if teks_list[1] in num_to_char:
            teks_list[1] = num_to_char[teks_list[1]]

    if teks_list[-1] in num_to_char:
        teks_list[-1] = num_to_char[teks_list[-1]]
        
    return "".join(teks_list)

class VisionNodeYOLO:
    def __init__(self, yolo_model="yolov10n.pt", plc_ip="127.0.0.1", plc_port=502):
        print("[INFO] Memeriksa GPU...")
        self.device = 0 if torch.cuda.is_available() else "cpu"
        print(f"[INFO] YOLO berjalan di: {'GPU (NVIDIA)' if self.device == 0 else 'CPU'}")
        
        self.detector = YOLO(yolo_model)
        self.vehicle_classes = [2, 5, 7] 
        
        print("[INFO] Memuat model PaddleOCR...")
        self.ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
        
        # ==========================================
        # INISIALISASI DATABASE & ANTI-SPAM
        # ==========================================
        # Ini simulasi database. Ganti dengan plat truk yang kamu punya untuk testing
        self.database_truk = ["BA8281HA", "B8888ZZ", "BK123AB"] 
        
        self.plat_terakhir = ""
        self.waktu_scan_terakhir = 0
        self.cooldown_detik = 10 
        
        # ==========================================
        # INISIALISASI KONEKSI PLC (MODBUS TCP)
        # ==========================================
        print(f"[INFO] Mencoba terhubung ke OpenPLC di {plc_ip}:{plc_port}...")
        self.plc_client = ModbusTcpClient(plc_ip, port=plc_port)
        if self.plc_client.connect():
            print("[SUKSES] Terhubung ke OpenPLC!")
        else:
            print("[WARNING] Gagal terhubung ke OpenPLC. Cek IP/Port atau pastikan OpenPLC menyala.")

    def process_frame(self, frame):
        results = self.detector.predict(
            frame,
            conf=0.5,
            verbose=False,
            device=self.device,
        )
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_id = int(box.cls[0])
                
                if class_id in self.vehicle_classes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    cv2.putText(frame, "KENDARAAN", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                    
                    tinggi_kendaraan = y2 - y1
                    bumper_y1 = y1 + int(tinggi_kendaraan * 0.65) 
                    bumper_y2 = y2
                    bumper_x1 = x1
                    bumper_x2 = x2
                    
                    cv2.rectangle(frame, (bumper_x1, bumper_y1), (bumper_x2, bumper_y2), (0, 255, 255), 3)
                    
                    bumper_crop = frame[bumper_y1:bumper_y2, bumper_x1:bumper_x2]
                    
                    if bumper_crop.size != 0:
                        ocr_result = self.ocr.ocr(bumper_crop, cls=True)
                        
                        teks_plat = ""
                        if ocr_result and ocr_result[0]:
                            for line in ocr_result[0]:
                                if line and len(line) >= 2:
                                    text_data = line[1]
                                    if float(text_data[1]) > 0.6: 
                                        teks_plat += str(text_data[0])
                            
                            teks_kasar = re.sub(r'[^A-Z0-9]', '', teks_plat.upper())
                            plat_bersih = koreksi_plat_indo(teks_kasar)
                            
                            if len(plat_bersih) >= 4:
                                cv2.putText(frame, f"PLAT: {plat_bersih}", (bumper_x1, bumper_y1 - 10), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                                
                                # ==========================================
                                # LOGIKA ANTI-SPAM & KIRIM KE PLC
                                # ==========================================
                                waktu_sekarang = time.time()
                                
                                if plat_bersih != self.plat_terakhir or (waktu_sekarang - self.waktu_scan_terakhir) > self.cooldown_detik:
                                    print(f"\n=====================================")
                                    print(f">>> [DETEKSI BARU] Plat: {plat_bersih}")
                                    
                                    # Update memori Anti-Spam
                                    self.plat_terakhir = plat_bersih
                                    self.waktu_scan_terakhir = waktu_sekarang
                                    
                                    # Cek Database
                                    if plat_bersih in self.database_truk:
                                        print(f">>> [STATUS] Akses DITERIMA. Terdaftar di Database.")
                                        try:
                                            # Tulis nilai 1 (True) ke Coil address 0 di OpenPLC
                                            self.plc_client.write_coil(0, True) 
                                            print(">>> [MODBUS] Sinyal '1' dikirim ke PLC (Buka Palang).")
                                        except Exception as e:
                                            print(f">>> [MODBUS ERROR] Gagal mengirim data: {e}")
                                            
                                    else:
                                        print(f">>> [STATUS] Akses DITOLAK. Plat tidak dikenal.")
                                        try:
                                            # Tulis nilai 0 (False) ke Coil address 0 di OpenPLC
                                            self.plc_client.write_coil(0, False)
                                            print(">>> [MODBUS] Sinyal '0' dikirim ke PLC (Akses Ditolak).")
                                        except Exception as e:
                                            print(f">>> [MODBUS ERROR] Gagal mengirim data: {e}")
                                    print(f"=====================================")

        return frame

if __name__ == "__main__":
    # Ganti IP ini dengan IP komputer tempat OpenPLC berjalan
    yolo_system = VisionNodeYOLO(yolo_model="yolov10n.pt", plc_ip="127.0.0.1", plc_port=5020)
    
    MODE_INPUT = "KAMERA"
    
    if MODE_INPUT == "GAMBAR":
        # ... (Logika gambar tetap sama) ...
        pass

    elif MODE_INPUT == "KAMERA":
        print(f"\n[INFO] Menjalankan Mode KAMERA (/dev/video{CAMERA_SOURCE})")
        cap = open_video_capture(CAMERA_SOURCE)
        if not cap.isOpened():
            print("[ERROR] Kamera tidak ditemukan.")
            exit()
            
        print("[SUKSES] Kamera Aktif! Tekan 'q' pada keyboard untuk keluar.")
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            processed_frame = yolo_system.process_frame(frame)
            cv2.imshow("DEMO YOLO & OCR - JEMBATAN TIMBANG", processed_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cap.release()
        cv2.destroyAllWindows()