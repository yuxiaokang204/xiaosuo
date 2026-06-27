@echo off
set NODE_PATH=C:\Program Files\nodejs
set PATH=%NODE_PATH%;%PATH%
echo Starting frontend dev server on http://localhost:8080...
npm run dev
