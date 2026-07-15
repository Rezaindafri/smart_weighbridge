PROGRAM main
  VAR
    Volume_Locked : UINT;
    Weight_Locked : UINT;
  END_VAR
  VAR
    PC_ANPR_Truk_Detected AT %QX0.0 : BOOL;
    S1_LiDAR_Posisi AT %QX0.1 : BOOL;
    S2_LoadCell_Stable AT %QX0.2 : BOOL;
    Reset_Button AT %QX0.3 : BOOL;
    Palang_masuk AT %QX0.4 : BOOL;
    Sistem_Ready AT %QX0.5 : BOOL;
    Alarm_Posisi AT %QX0.6 : BOOL;
    Lock_Data AT %QX0.7 : BOOL;
    LiDAR_Volume_Raw AT %QW1 : UINT;
    LoadCell_Weight_Raw AT %QW2 : UINT;
    Database_Tare_Weight AT %QW3 : UINT;
    Netto_Weight AT %QW4 : UINT;
    Density_Result AT %QW5 : UINT;
  END_VAR
  VAR
    _TMP_MOVE7232109_ENO : BOOL;
    _TMP_MOVE7232109_OUT : UINT;
    _TMP_MOVE10839463_ENO : BOOL;
    _TMP_MOVE10839463_OUT : UINT;
    _TMP_SUB3982664_ENO : BOOL;
    _TMP_SUB3982664_OUT : UINT;
    _TMP_DIV463620_ENO : BOOL;
    _TMP_DIV463620_OUT : UINT;
  END_VAR

  Palang_masuk := PC_ANPR_Truk_Detected AND NOT(Lock_Data);
  Sistem_Ready := NOT(Lock_Data);
  Alarm_Posisi := NOT(S1_LiDAR_Posisi) AND PC_ANPR_Truk_Detected;
  Lock_Data := NOT(Reset_Button) AND (Lock_Data OR S2_LoadCell_Stable AND S1_LiDAR_Posisi AND PC_ANPR_Truk_Detected);
  _TMP_MOVE7232109_OUT := MOVE(EN := Lock_Data, IN := LiDAR_Volume_Raw, ENO => _TMP_MOVE7232109_ENO);
  IF _TMP_MOVE7232109_ENO THEN
      Volume_Locked := _TMP_MOVE7232109_OUT;
  END_IF;
  _TMP_MOVE10839463_OUT := MOVE(EN := Lock_Data, IN := LoadCell_Weight_Raw, ENO => _TMP_MOVE10839463_ENO);
  IF _TMP_MOVE10839463_ENO THEN
      Weight_Locked := _TMP_MOVE10839463_OUT;
  END_IF;
  _TMP_SUB3982664_OUT := SUB(EN := Lock_Data, IN1 := Weight_Locked, IN2 := Database_Tare_Weight, ENO => _TMP_SUB3982664_ENO);
  IF _TMP_SUB3982664_ENO THEN
      Netto_Weight := _TMP_SUB3982664_OUT;
  END_IF;
  _TMP_DIV463620_OUT := DIV(EN := Lock_Data, IN1 := Netto_Weight, IN2 := Volume_Locked, ENO => _TMP_DIV463620_ENO);
  IF _TMP_DIV463620_ENO THEN
      Density_Result := _TMP_DIV463620_OUT;
  END_IF;
END_PROGRAM


CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#20ms,PRIORITY := 1);
    PROGRAM instance0 WITH task0 : main;
  END_RESOURCE
END_CONFIGURATION
