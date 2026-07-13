@echo off
REM Build Teufort Toolkit into a single-file Windows .exe.
REM Requires: pip install -r requirements.txt pyinstaller

echo [1/2] Ikon uretiliyor...
python assets\make_icon.py
if errorlevel 1 goto :error

echo [2/2] EXE derleniyor...
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "Teufort Toolkit" --icon "assets\icon.ico" ^
  --add-data "assets\icon.ico;assets" ^
  --add-data "assets\samples;assets\samples" ^
  --collect-all customtkinter --collect-all soundfile --collect-all sounddevice ^
  --exclude-module scipy main.py
if errorlevel 1 goto :error

echo.
echo Tamamlandi: dist\Teufort Toolkit.exe
goto :eof

:error
echo.
echo HATA: derleme basarisiz oldu.
exit /b 1
