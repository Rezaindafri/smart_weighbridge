PROGRAM main
  VAR_INPUT
    S1_LiDAR_Posisi : BOOL;
    S2_LoadCell_Stable : BOOL;
    Reset_Button : BOOL;
    LiDAR_Volume_Raw : INT;
    LoadCell_Weight_Raw : INT;
  END_VAR
  VAR_OUTPUT
    Sistem_Ready : BOOL;
    Alarm_Posisi : BOOL;
    Density_Result : REAL;
  END_VAR
  VAR
    Lock_Data : BOOL;
    Volume_Locked : REAL;
    Weight_Locked : REAL;
    R_TRIG1 : R_TRIG;
    _TMP_MOVE7232109_ENO : BOOL;
    _TMP_MOVE7232109_OUT : INT;
    R_TRIG2 : R_TRIG;
    _TMP_MOVE10839463_ENO : BOOL;
    _TMP_MOVE10839463_OUT : INT;
    _TMP_DIV463620_ENO : BOOL;
    _TMP_DIV463620_OUT : REAL;
  END_VAR

  Sistem_Ready := NOT(Lock_Data);
  Alarm_Posisi := NOT(S1_LiDAR_Posisi);
  Lock_Data := NOT(Reset_Button) AND (Lock_Data OR S2_LoadCell_Stable AND S1_LiDAR_Posisi);
  R_TRIG1(CLK := Lock_Data);
  _TMP_MOVE7232109_OUT := MOVE(EN := R_TRIG1.Q, IN := LiDAR_Volume_Raw, ENO => _TMP_MOVE7232109_ENO);
  IF _TMP_MOVE7232109_ENO THEN
      Volume_Locked := _TMP_MOVE7232109_OUT;
  END_IF;
  R_TRIG2(CLK := Lock_Data);
  _TMP_MOVE10839463_OUT := MOVE(EN := R_TRIG2.Q, IN := LoadCell_Weight_Raw, ENO => _TMP_MOVE10839463_ENO);
  IF _TMP_MOVE10839463_ENO THEN
      Weight_Locked := _TMP_MOVE10839463_OUT;
  END_IF;
  _TMP_DIV463620_OUT := DIV(EN := Lock_Data, IN1 := Weight_Locked, IN2 := Volume_Locked, ENO => _TMP_DIV463620_ENO);
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
