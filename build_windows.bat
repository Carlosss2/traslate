@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Traductor LSM - Compilacion para Windows
echo ============================================================
echo.

set "PYTHON_CMD="

py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.12"

if not defined PYTHON_CMD (
    py -3.13 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3.13"
)

if not defined PYTHON_CMD (
    python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13)) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ERROR: No se encontro Python 3.12 o 3.13.
    echo.
    echo Instala Python desde https://www.python.org/downloads/windows/
    echo Marca la opcion "Add python.exe to PATH" durante la instalacion.
    echo No uses Python 3.14: PyAudio todavia no tiene instalador para esa version.
    echo.
    pause
    exit /b 1
)

echo Usando: %PYTHON_CMD%
echo.

if not exist ".build-venv\Scripts\python.exe" (
    echo Creando entorno de compilacion...
    %PYTHON_CMD% -m venv .build-venv
    if errorlevel 1 goto :error
)

call ".build-venv\Scripts\activate.bat"
if errorlevel 1 goto :error

echo Actualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo Instalando dependencias...
pip install -r requirements-build.txt
if errorlevel 1 goto :error

echo.
echo Generando ejecutable...
python -m PyInstaller --noconfirm --clean traductor.spec
if errorlevel 1 goto :error

if not exist "dist\Traductor_LSM\Traductor_LSM.exe" (
    echo ERROR: No se genero el ejecutable esperado.
    goto :error
)

echo.
echo Creando paquete ZIP...
if exist "dist\Traductor_LSM_windows.zip" del /q "dist\Traductor_LSM_windows.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\Traductor_LSM\*' -DestinationPath 'dist\Traductor_LSM_windows.zip' -Force"
if errorlevel 1 goto :error

powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -LiteralPath 'dist\Traductor_LSM_windows.zip' -Algorithm SHA256).Hash | Out-File -FilePath 'dist\Traductor_LSM_windows.zip.sha256' -Encoding ascii"

echo.
echo ============================================================
echo   LISTO
echo ============================================================
echo Ejecutable: dist\Traductor_LSM\Traductor_LSM.exe
echo ZIP portable: dist\Traductor_LSM_windows.zip
echo Hash SHA256: dist\Traductor_LSM_windows.zip.sha256
echo.
echo IMPORTANTE: distribuye la carpeta completa, no solo el .exe.
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo   ERROR: la compilacion no termino correctamente
echo ============================================================
echo Revisa los mensajes anteriores. Si el error menciona PyAudio,
echo instala Python 3.12 y vuelve a ejecutar este archivo.
echo.
pause
exit /b 1
