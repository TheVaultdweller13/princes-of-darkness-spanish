@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo Reemplazando "english" por "spanish" en los nombres de archivo...
echo.

for /r %%F in (*english*) do (
    set "name=%%~nxF"
    set "newname=!name:english=spanish!"
    if not "!name!"=="!newname!" (
        if not exist "%%~dpF!newname!" (
            echo Renombrando: "%%F" --^> "!newname!"
            ren "%%F" "!newname!"
        ) else (
            echo Omitiendo "%%F" porque "!newname!" ya existe.
        )
    )
)

echo.
echo Listo.
pause