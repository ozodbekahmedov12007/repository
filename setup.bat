@echo off
echo Python 3.11 ni tekshirish...
py -3.11 --version
if errorlevel 1 (
    echo Python 3.11 topilmadi!
    echo https://www.python.org/downloads/release/python-3110/ dan yuklab o'rnating
    pause
    exit /b
)

echo Eski venv o'chirilmoqda...
rmdir /s /q venv 2>nul

echo Yangi virtual environment yaratilmoqda...
py -3.11 -m venv venv311

echo Aktivlashtirish...
call venv311\Scripts\activate.bat

echo Pip yangilanmoqda...
python -m pip install --upgrade pip

echo Paketlar o'rnatilmoqda...
pip install groq==0.5.0
pip install flask flask-cors yt-dlp schedule edge-tts google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv gunicorn

echo Bot ishga tushirilmoqda...
python app.py

pause