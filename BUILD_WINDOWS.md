# Generar el ejecutable para Windows

La aplicación se empaqueta con **PyInstaller** en modo carpeta (`--onedir`).
Esto produce una carpeta con `Traductor_LSM.exe` y sus archivos de apoyo.

> Importante: el `.exe` debe compilarse con **Python de Windows**. No se puede
> generar un `.exe` nativo desde macOS o Linux de forma confiable. Por eso se
> incluyen dos caminos: compilarlo en la laptop Windows o usar GitHub Actions.

## Opción A: compilar en una laptop Windows (recomendado)

### Requisitos

- Windows 10 u 11 de 64 bits.
- Python **3.12** o **3.13** para Windows.
  - Descárgalo de <https://www.python.org/downloads/windows/>
  - Durante la instalación marca **Add python.exe to PATH**.
  - No uses Python 3.14: PyAudio todavía no publica instalador para esa versión.
- Conexión a internet para descargar las dependencias.

### Pasos

1. Copia la carpeta completa del proyecto a la laptop Windows.
2. Haz doble clic en `build_windows.bat`.
3. Espera a que termine. La primera vez tarda varios minutos.
4. Al final tendrás:
   - `dist\Traductor_LSM\Traductor_LSM.exe`
   - `dist\Traductor_LSM_windows.zip` (para llevar a otra laptop)
   - `dist\Traductor_LSM_windows.zip.sha256` (huella de integridad)

Para usar el programa, abre la carpeta `dist\Traductor_LSM` y ejecuta
`Traductor_LSM.exe`. **No muevas el `.exe` solo**: necesita los archivos que
están a su lado.

### Si falla PyAudio

Instala Python 3.12 y vuelve a ejecutar `build_windows.bat`. El script elige
automáticamente 3.12 si está disponible.

## Opción B: compilar con GitHub Actions

Si subes el proyecto a GitHub, el archivo
`.github/workflows/build-windows.yml` compila el `.exe` en un servidor Windows
oficial de GitHub:

1. Sube el proyecto a un repositorio de GitHub.
2. Entra a **Actions** > **Compilar ejecutable de Windows**.
3. Pulsa **Run workflow**.
4. Cuando termine, descarga el artefacto **Traductor_LSM_windows**.
5. Descomprime el ZIP y ejecuta `Traductor_LSM.exe`.

También se ejecuta automáticamente al publicar una etiqueta `v1.1.0` o similar.

## Sobre la seguridad

- El ejecutable se genera a partir del código de este proyecto y de paquetes
  oficiales instalados con `pip`.
- Se usa modo carpeta en lugar de un solo archivo porque los `.exe`
  autocontenidos se marcan con más frecuencia como sospechosos y tardan más en
  arrancar.
- El `.exe` **no está firmado digitalmente**. Windows puede mostrar SmartScreen
  la primera vez. Para continuar: **Más información** > **Ejecutar de todas
  formas**.
- Si vas a distribuirlo en muchas computadoras, lo ideal es firmarlo con un
  certificado de firma de código. Sin ese certificado no es posible evitar el
  aviso de SmartScreen.
- Puedes verificar el ZIP con el archivo `.sha256`:

```powershell
Get-FileHash .\Traductor_LSM_windows.zip -Algorithm SHA256
```

El resultado debe coincidir con el contenido de
`Traductor_LSM_windows.zip.sha256`.

## Qué incluye el paquete

- `Traductor_LSM.exe`: la aplicación.
- `config.json`: configuración.
- `data\diccionario.json`: diccionario completo.
- `data\señas\` y `data\alfabeto\`: aquí se agregan los GIF/imágenes.
- `LEEME_EJECUTABLE.txt`: instrucciones para el usuario final.
- Librerías de PyQt6, SpeechRecognition y PyAudio.

## Agregar o actualizar señas después de compilar

Puedes copiar los GIF directamente en:

```
dist\Traductor_LSM\data\señas\
dist\Traductor_LSM\data\alfabeto\
```

Los nombres deben coincidir con el diccionario, por ejemplo `hola.gif`,
`gracias.gif` o `letra_a.gif`. No hace falta volver a compilar.
