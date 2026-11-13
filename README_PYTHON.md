# Traductor Voz a Lengua de Señas Chiapaneca / LSM

Aplicación de escritorio en Python con PyQt6 para traducir voz a Lengua de Señas Mexicana y Lengua de Señas Chiapaneca.

## Características

### Reconocimiento de Voz en Tiempo Real
- Usa SpeechRecognition con Google Speech API (es-MX)
- Botón de micrófono con estados visuales
- Ajuste automático de ruido ambiente
- Funciona offline con diccionario local

### Transcripción y Procesamiento
- Panel de transcripción en vivo
- Contador de palabras
- Procesamiento inteligente con detección de frases de 2 palabras
- **Deletreo dactilológico automático** para palabras no encontradas

### Traducción Grande para Proyector
- Panel principal con la frase traducida en letras grandes (hasta 240 pt)
- El tamaño de letra se ajusta automáticamente al largo de la frase
- Botones A- / A+ para aumentar o reducir el texto manualmente
- Fondo blanco y letras negras de alto contraste para proyectar en el salón

### Visor de Señas Compacto
- Panel pequeño en la parte inferior con la seña actual
- Muestra imagen o GIF si existe en `data/señas/` o `data/alfabeto/`
- Si no hay imagen, muestra la descripción y la variante regional
- Cola de reproducción automática
- Soporte para palabras clave chiapanecas con variantes regionales
- Indicador visual: Seña completa vs Deletreo dactilológico
- Controles funcionales: Reproducir/Pausar, Anterior/Siguiente, Detener
- Doble clic en la cola para saltar a cualquier seña
- Control de velocidad: 0.5x, 1.0x, 1.5x, 2.0x
- Barra de progreso

### Modo Proyector
- Oculta menús, barra lateral, barra de estado y entra en pantalla completa
- Actívalo con F11 o con el botón "Modo proyector"
- Sal con Esc o F11
- Atajos: Espacio (reproducir/pausar), flechas (anterior/siguiente),
  Ctrl+L (limpiar pantalla)

### Diccionario Completo
- **+36,000 palabras** en diccionario local
- **1,320 palabras** con variante regional Chiapaneca
- **34,965 palabras** Nacional LSM
- Alfabeto dactilológico completo (a-z, ñ)
- Gestor de diccionario para agregar señas personalizadas
- Búsqueda y filtrado por región
- Estadísticas del diccionario

### Accesibilidad
- Tema claro de alto contraste: fondo blanco y letras negras
- Modo proyector a pantalla completa
- Simulador de voz y campo de texto para pruebas sin micrófono
- Interfaz intuitiva en español
- Diseño adaptable

## Instalación

### Requisitos
- Python 3.10+ (lo requiere PyQt6)
- Micrófono funcional
- Conexión a internet (para reconocimiento de voz con Google)
- FLAC instalado en el sistema (ver [Instalar FLAC](#instalar-flac-reconocimiento-de-voz))

### Instalar dependencias
```bash
pip install -r requirements.txt
```

### Instalar FLAC (reconocimiento de voz)

`SpeechRecognition` convierte el audio a FLAC antes de enviarlo a Google. Si no
encuentra el comando `flac` en el sistema, usa un binario incluido en el paquete
que **solo funciona en Macs Intel**. En Apple Silicon (M1/M2/M3/M4) eso produce
el error:

```
[Errno 86] Bad CPU type in executable: .../speech_recognition/flac-mac
```

Actualizar `SpeechRecognition` **no** corrige el problema: incluso la versión más
reciente sigue incluyendo el mismo binario x86_64. Hay que instalar FLAC nativo:

| Sistema | Comando |
| --- | --- |
| macOS (Homebrew) | `brew install flac` |
| Windows (winget) | `winget install --id Xiph.FLAC` |
| Windows (Chocolatey) | `choco install flac` |
| Windows (Scoop) | `scoop install flac` |
| Linux (Debian/Ubuntu) | `sudo apt install flac` |
| Linux (Fedora) | `sudo dnf install flac` |

Verifica que quedó disponible:

```bash
flac --version
```

`main.py` detecta automáticamente las rutas habituales de Homebrew
(`/opt/homebrew/bin`), MacPorts, winget, Chocolatey, Scoop y `Program Files`.
Así la aplicación funciona también al abrirla desde Finder o desde un IDE, donde
el `PATH` suele ser más limitado que en la Terminal.

> **Windows:** usa Python 3.12 o 3.13. PyAudio 0.2.14 todavía no publica wheels
> para Python 3.14, así que `pip install pyaudio` intentaría compilar desde el
> código fuente y necesitarías Visual Studio Build Tools.

### Generar diccionario (ya incluido)
```bash
python generate_dictionary.py
```

### Ejecutar aplicación
```bash
python main.py
```

## Uso

1. **Iniciar escucha**: Presiona "Iniciar escucha" o usa el menú
2. **Hablar**: Di tu frase en español mexicano
3. **Ver traducción**: La frase aparece en grande y las señas se reproducen
   automáticamente en el panel inferior
4. **Controlar reproducción**: Usa los botones o las flechas del teclado
5. **Ajustar letras**: Usa A- / A+ o el menú Ver según la distancia del proyector
6. **Proyectar**: Presiona F11 o "Modo proyector" y sal con Esc
7. **Probar sin micrófono**: Escribe una frase en el campo de texto o usa
   "Simular voz"
8. **Administrar diccionario**: Menú Diccionario > Gestionar diccionario

## Estructura

```
lenguaje/
├── main.py                 # Aplicación principal PyQt6
├── generate_dictionary.py  # Generador de diccionario
├── requirements.txt        # Dependencias
├── config.json            # Configuración
├── README_PYTHON.md       # Este archivo
└── data/
    ├── diccionario.json   # Diccionario con 36000+ palabras
    ├── señas/            # Archivos GIF/Video de señas
    └── alfabeto/         # Archivos del alfabeto dactilológico
```

## Palabras Clave Soportadas

- **Saludos**: hola, buenos días, buenas tardes, buenas noches, adiós, bienvenido
- **Cortesía**: gracias, por favor
- **Preguntas**: cómo estás, qué, cuándo, dónde
- **Respuestas**: sí, no, bien, mal, más o menos
- **Personas**: amigo/a, familia, madre/padre, hermano/hermana, tío/tía
- **Lugares**: Chiapas, casa, escuela, hospital, mercado, iglesia, comunidad, pueblo
- **Necesidades**: ayuda, necesito, comer, beber, agua, comida, medicina, trabajo, dinero
- **Números**: uno al diez

## Tecnologías

- **PyQt6**: Interfaz gráfica nativa
- **SpeechRecognition**: Reconocimiento de voz
- **PyAudio**: Captura de audio
- **JSON**: Almacenamiento de diccionario
- **Threading**: Procesamiento concurrente

## Notas

- El reconocimiento de voz requiere internet para usar Google Speech API
- Las imágenes/GIFs de señas deben agregarse manualmente en `data/señas/`
- El diccionario es completamente extensible desde la aplicación
- Diseñado para uso offline una vez cargado el diccionario

## Desarrollado para

Proyecto CECYT - Promoción de la inclusión y accesibilidad para la comunidad sorda de Chiapas.
