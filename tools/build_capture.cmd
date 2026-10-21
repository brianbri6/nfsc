@call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
cl /nologo /O2 nfsco_capture.c /link /FIXED /BASE:0x30000000 /DYNAMICBASE:NO
