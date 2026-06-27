@echo off
set NODE_PATH=C:\Program Files\nodejs
set PATH=%NODE_PATH%;%PATH%
echo Installing npm dependencies...
call npm install
echo Done.
