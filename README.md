# Transcrição de Áudio, Vídeo e YouTube com Whisper

Aplicação Python para converter vídeos locais ou links do YouTube para áudio (`.mp3` ou `.m4a`) e transcrever automaticamente para texto (`.txt`) utilizando o modelo Whisper da OpenAI.

## Funcionalidades

- Seleção de ficheiros locais de áudio (`.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`, `.aac`, `.wma`, `.opus`) ou vídeo (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, etc.).
- Download e conversão automática de links do YouTube (e outros URLs suportados pelo `yt-dlp`) para `.mp3` ou `.m4a`.
- Conversão local de ficheiros de vídeo para `.mp3` ou `.m4a` utilizando o FFmpeg.
- Transcrição automática com Whisper (em português por defeito, com opção de escolher modelo e idioma).
- Opção de apenas converter para áudio ou converter e transcrever para `.txt`.
- Processamento local da transcrição, sem enviar áudio para serviços cloud.
- Exportação automática da transcrição para `<nome>_transcricao.txt` na mesma pasta do áudio.

## Requisitos

- Python 3.9 ou superior.
- FFmpeg instalado e disponível no `PATH`.
- Ligação à Internet para descarregar links do YouTube e, na primeira utilização, descarregar o modelo Whisper.
- Memória RAM suficiente para executar o modelo escolhido.

## Instalação

### 1. Instalar o FFmpeg

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

Windows:

```bash
winget install Gyan.FFmpeg
```

macOS:

```bash
brew install ffmpeg
```

### 2. Instalar dependências Python

```bash
pip install -r requirement.txt
```

### 3. Executar o programa

```bash
python transcrever.py
```

## Utilização

1. Executar `python transcrever.py`.
2. Escolher a origem:
   - **Ficheiro local (Áudio ou Vídeo)**: clicar em **Procurar...** para selecionar o ficheiro.
   - **Link do YouTube / Vídeo online**: colar o link e escolher a pasta de destino.
3. Escolher o formato de conversão (`.mp3` ou `.m4a`), o modelo Whisper e o idioma.
4. Clicar em **Iniciar** e aguardar o processamento.
5. O ficheiro convertido (quando aplicável) e o ficheiro `<nome>_transcricao.txt` serão guardados na respetiva pasta.

## Modelos Whisper

O programa utiliza o modelo `medium` por defeito.

| Modelo | Velocidade | Precisão |
| --- | --- | --- |
| `tiny` | Muito rápida | Básica |
| `base` | Rápida | Razoável |
| `small` | Média | Boa |
| `medium` | Mais lenta | Muito boa |
| `large` | Lenta | Elevada |

## Estrutura do projeto

```text
transcrever/
│
├── transcrever.py
├── requirement.txt
└── README.md
```

## Tecnologia

- Python
- OpenAI Whisper
- FFmpeg
- yt-dlp
- Tkinter

> Nota: o `tkinter` normalmente já vem incluído no Python. Em algumas distribuições Linux, poderá ser necessário instalá-lo separadamente (`sudo apt install python3-tk`).
