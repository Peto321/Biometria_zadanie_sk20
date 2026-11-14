@echo off
cd /d "%~dp0"

if not exist venv (
  echo Vytvaram virtualne prostredie
  python -m venv venv
  if errorlevel 1 (
    pause
    exit /b 1
  )
)

call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python opencv-contrib-python-headless
pip install "opencv-contrib-python<5"

echo.
python -c "import cv2; print('OpenCV', cv2.__version__); print(cv2.CascadeClassifier)"
python -c "import deepface, mediapipe; print('deepface + mediapipe OK')"

echo.
echo Hotovo. Aplikacia sa spusti cez start_app.bat
pause
