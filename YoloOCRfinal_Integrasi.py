import cv2
import torch
import re 
import time
import mysql.connector
from ultralytics import YOLO
from paddleocr import PaddleOCR
from pymodbus.client import ModbusTcpClient

torch.backends.cudnn.enabled = False
print("[INFO] PyTorch cuDNN dinonaktifkan agar tidak bentrok dengan PaddleOCR.")

# ==========================================
# KONFIGURASI SISTEM
# ==========================================
CAMERA_SOURCE = 0 
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

DB_HOST = "localhost"
DB_USER = "rifki"
DB_PASS = "!Admin123"
DB_NAME = "smart_weighbridge"

PLC_IP = "127.0.0.1"
PLC_PORT = 5020

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
        self.device = 0 if torch.cuda.is_available() else "cpu"
        print(f"[INFO] YOLO berjalan di: {'GPU (NVIDIA)' if self.device == 0 else 'CPU'}")
        
        self.detector = YOLO(yolo_model)
        self.vehicle_classes = [2, 5, 7] 
        self.ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
        
        # Inisialisasi Database
        try:
            self.db = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
            )
            self.cursor = self.db.cursor()
            print("[INFO] Sukses terhubung ke Database MySQL.")
        except Exception as e:
            print(f"[ERROR] Gagal terhubung ke database: {e}")
            exit()
        
        # Anti-Spam
        self.plat_terakhir = ""
        self.waktu_scan_terakhir = 0
        self.cooldown_detik = 10 
        
        # Inisialisasi PLC
        print(f"[INFO] Mencoba terhubung ke OpenPLC di {plc_ip}:{plc_port}...")
        self.plc_client = ModbusTcpClient(plc_ip, port=plc_port)
        if self.plc_client.connect():
            print("[INFO] Sukses terhubung ke OpenPLC!")
            # Pastikan semua kondisi bersih sebelum mulai
            self.plc_client.write_coils(address=0, values=[False, False, False, False])
        else:
            print("[WARNING] Gagal terhubung ke OpenPLC.")

    def jalankan_simulasi_plc(self, plat_nomor, tare_weight):
        """Fungsi untuk menjalankan workflow perhitungan ke PLC berdasarkan Ladder Diagram"""
        # --- 1. SIMULASI NILAI SENSOR (Bisa diganti pembacaan real nantinya) ---
        volume_simulasi = 25    # m3 (Register 1)
        gross_weight = 55000    # kg (Register 2)
        
        print(f">>> [PLC] Memulai proses perhitungan untuk Plat: {plat_nomor}")

        # --- 2. KIRIM DATA ANALOG KE REGISTER PLC ---
        # Address 1 (%QW1 = Vol), Address 2 (%QW2 = Gross), Address 3 (%QW3 = Tare)
        payload = [volume_simulasi, gross_weight, tare_weight]
        resp_reg = self.plc_client.write_registers(address=1, values=payload)
        
        if resp_reg.isError():
             print("[ERROR] Gagal menulis data raw ke PLC!")
             return
             
        time.sleep(0.5)

        # --- 3. TRIGGER SENSOR DIGITAL SEKALIGUS ---
        # Address 0 (ANPR), Address 1 (LiDAR), Address 2 (LoadCell) dihidupkan (True)
        print("[PLC] Menekan saklar ANPR, LiDAR, dan LoadCell...")
        self.plc_client.write_coils(address=0, values=[True, True, True])
        
        # Beri waktu jeda agar Ladder mengeksekusi fungsi MOVE, SUB, DIV dan Lock_Data mengunci
        time.sleep(2) 

        # --- 4. BACA HASIL DARI PLC ---
        # Address 4 (%QW4 = Netto) dan Address 5 (%QW5 = Density)
        diagnostic_read = self.plc_client.read_holding_registers(address=4, count=2)

        if not diagnostic_read.isError():
            netto_out = diagnostic_read.registers[0]    
            density_out = diagnostic_read.registers[1]  

            print(f"\n--- [HASIL AKHIR KALKULASI] ---")
            print(f"Berat Kotor (Gross)    : {gross_weight} kg")
            print(f"Berat Kosong (Tare)    : {tare_weight} kg")
            print(f"Berat Isi (Netto) PLC  : {netto_out} kg")
            print(f"Volume Muatan PLC      : {volume_simulasi} m3")
            print(f"Massa Jenis PLC        : {density_out} kg/m3")

            # --- 5. SIMPAN KE DATABASE LOG ---
            if netto_out > 0:
                query_insert = "INSERT INTO log_penimbangan (plat_nomor, gross_weight, netto_weight, volume, density) VALUES (%s, %s, %s, %s, %s)"
                self.cursor.execute(query_insert, (plat_nomor, gross_weight, netto_out, volume_simulasi, density_out))
                self.db.commit()
                print("[DATABASE] Data sukses disimpan ke log_penimbangan.")
            else:
                print("[WARN] Nilai Netto masih 0. Cek kembali Ladder Diagram!")
        else:
            print("[ERROR] Gagal membaca hasil register dari PLC.")

        # --- 6. RESET SISTEM PLC (Standby) ---
        print("[RESET] Jembatan Timbang kembali Standby.")
        # Matikan ANPR, LiDAR, LC (0,1,2 = False), Hidupkan Reset_Button (3 = True)
        self.plc_client.write_coils(address=0, values=[False, False, False, True])
        time.sleep(1)
        # Lepas tombol reset
        self.plc_client.write_coil(address=3, value=False)
        print("=====================================\n")


    def process_frame(self, frame):
        results = self.detector.predict(frame, conf=0.5, verbose=False, device=self.device)
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_id = int(box.cls[0])
                
                if class_id in self.vehicle_classes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    
                    tinggi_kendaraan = y2 - y1
                    bumper_y1 = y1 + int(tinggi_kendaraan * 0.65) 
                    bumper_y2 = y2
                    
                    cv2.rectangle(frame, (x1, bumper_y1), (x2, bumper_y2), (0, 255, 255), 3)
                    bumper_crop = frame[bumper_y1:bumper_y2, x1:x2]
                    
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
                                cv2.putText(frame, f"PLAT: {plat_bersih}", (x1, bumper_y1 - 10), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                                
                                waktu_sekarang = time.time()
                                if plat_bersih != self.plat_terakhir or (waktu_sekarang - self.waktu_scan_terakhir) > self.cooldown_detik:
                                    print(f"\n=====================================")
                                    print(f">>> [DETEKSI BARU] Plat Kamera: {plat_bersih}")
                                    
                                    self.plat_terakhir = plat_bersih
                                    self.waktu_scan_terakhir = waktu_sekarang
                                    
                                    # CEK KE DATABASE MASTER TRUK
                                    query_cek = "SELECT tare_weight FROM data_truk WHERE plat_nomor = %s"
                                    self.cursor.execute(query_cek, (plat_bersih,))
                                    db_result = self.cursor.fetchone()
                                    
                                    if db_result:
                                        tare_weight_db = db_result[0]
                                        print(f">>> [STATUS] Akses DITERIMA. Plat terdaftar di Database.")
                                        
                                        # Trigger fungsi penggabungan PLC & Database logging
                                        self.jalankan_simulasi_plc(plat_bersih, tare_weight_db)
                                    else:
                                        print(f">>> [STATUS] Akses DITOLAK. Plat tidak dikenal.")
                                        try:
                                            self.plc_client.write_coil(address=0, value=False)
                                        except Exception as e:
                                            pass
                                        print("=====================================\n")
        return frame

if __name__ == "__main__":
    yolo_system = VisionNodeYOLO(yolo_model="yolov10n.pt", plc_ip=PLC_IP, plc_port=PLC_PORT)
    
    print(f"\n[INFO] Menjalankan Mode KAMERA (/dev/video{CAMERA_SOURCE})")
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    
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