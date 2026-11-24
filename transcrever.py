import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

import whisper
import yt_dlp


AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".wma", ".opus"}
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".flv",
    ".wmv",
    ".m4v",
    ".mpeg",
    ".mpg",
    ".ts",
    ".3gp",
}
OUTPUT_FORMATS = ("mp3", "m4a")
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large")
LANGUAGE_OPTIONS = {
    "Português (pt)": "pt",
    "Auto-detetar": None,
    "Inglês (en)": "en",
    "Espanhol (es)": "es",
    "Francês (fr)": "fr",
}


def verificar_ffmpeg() -> str:
    """Verifica se o FFmpeg está disponível no PATH."""
    caminho = shutil.which("ffmpeg")
    if not caminho:
        raise RuntimeError(
            "FFmpeg não encontrado no PATH.\n"
            "Instale o FFmpeg antes de converter vídeo ou áudio."
        )
    return caminho


def converter_video_para_audio(caminho_origem: str, formato_saida: str = "mp3") -> str:
    """Converte um ficheiro de vídeo (ou áudio) para .mp3 ou .m4a usando FFmpeg."""
    formato = formato_saida.lower().lstrip(".")
    if formato not in OUTPUT_FORMATS:
        raise ValueError(f"Formato de saída não suportado: {formato_saida}")

    if not os.path.isfile(caminho_origem):
        raise FileNotFoundError(f"Ficheiro não encontrado: {caminho_origem}")

    ffmpeg_bin = verificar_ffmpeg()

    pasta = os.path.dirname(os.path.abspath(caminho_origem))
    nome = os.path.splitext(os.path.basename(caminho_origem))[0]
    caminho_audio = os.path.join(pasta, f"{nome}.{formato}")

    if os.path.abspath(caminho_origem) == os.path.abspath(caminho_audio):
        return caminho_audio

    codec_args = (
        ["-acodec", "libmp3lame", "-q:a", "2"]
        if formato == "mp3"
        else ["-acodec", "aac", "-b:a", "192k"]
    )

    comando = [
        ffmpeg_bin,
        "-y",
        "-i",
        caminho_origem,
        "-vn",
        *codec_args,
        caminho_audio,
    ]

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )

    if resultado.returncode != 0 or not os.path.isfile(caminho_audio):
        detalhe = (resultado.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError(
            "Falha ao converter ficheiro com FFmpeg:\n" + "\n".join(detalhe)
        )

    return caminho_audio


def descarregar_youtube_audio(
    url: str, pasta_destino: str, formato_saida: str = "mp3"
) -> str:
    """Descarrega o áudio de um link do YouTube (ou URL suportado) em .mp3 ou .m4a."""
    url_limpa = url.strip()
    if not url_limpa.startswith(("http://", "https://")):
        raise ValueError("Introduza um link válido começado por http:// ou https://")

    formato = formato_saida.lower().lstrip(".")
    if formato not in OUTPUT_FORMATS:
        raise ValueError(f"Formato de saída não suportado: {formato_saida}")

    verificar_ffmpeg()
    os.makedirs(pasta_destino, exist_ok=True)

    ficheiro_final: dict[str, str | None] = {"caminho": None}

    def postprocessor_hook(dados: dict) -> None:
        if dados.get("status") == "finished":
            caminho = dados.get("info_dict", {}).get("filepath")
            if caminho and caminho.lower().endswith(f".{formato}"):
                ficheiro_final["caminho"] = caminho

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(pasta_destino, "%(title)s.%(ext)s"),
        "windowsfilenames": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": formato,
                "preferredquality": "192",
            }
        ],
        "postprocessor_hooks": [postprocessor_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url_limpa, download=True)
        caminho = ficheiro_final["caminho"]
        if not caminho and info is not None:
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            caminho = f"{base}.{formato}"

    if not caminho or not os.path.isfile(caminho):
        raise RuntimeError(
            "Não foi possível localizar o ficheiro de áudio descarregado."
        )

    return caminho


def preparar_audio(
    origem: str,
    tipo_origem: str,
    formato_saida: str = "mp3",
    pasta_destino: str | None = None,
    converter_audio: bool = False,
) -> tuple[str, bool]:
    """Prepara o ficheiro de áudio para transcrição.

    Retorna (caminho_audio, foi_convertido_ou_descarregado).
    """
    if tipo_origem == "youtube":
        destino = pasta_destino or os.getcwd()
        caminho_audio = descarregar_youtube_audio(origem, destino, formato_saida)
        return caminho_audio, True

    if tipo_origem != "ficheiro":
        raise ValueError(f"Tipo de origem desconhecido: {tipo_origem}")

    if not os.path.isfile(origem):
        raise FileNotFoundError(f"Ficheiro não encontrado: {origem}")

    ext = os.path.splitext(origem)[1].lower()
    formato_normalizado = f".{formato_saida.lower().lstrip('.')}"

    if ext in AUDIO_EXTENSIONS and not (converter_audio and ext != formato_normalizado):
        return origem, False

    caminho_audio = converter_video_para_audio(origem, formato_saida)
    return caminho_audio, True


def transcrever_audio(
    caminho_audio: str,
    modelo: str = "medium",
    idioma: str | None = "pt",
    on_status=None,
) -> str:
    """Transcreve um ficheiro de áudio com Whisper e guarda o texto em TXT."""
    if not os.path.isfile(caminho_audio):
        raise FileNotFoundError(f"Ficheiro de áudio não encontrado: {caminho_audio}")

    pasta = os.path.dirname(os.path.abspath(caminho_audio))
    nome = os.path.splitext(os.path.basename(caminho_audio))[0]
    saida = os.path.join(pasta, f"{nome}_transcricao.txt")

    if on_status:
        on_status(f"A carregar modelo Whisper ({modelo})...")
    print(f"\nA carregar modelo Whisper ({modelo})...")
    print("Aguarde...\n")

    model = whisper.load_model(modelo, device="cpu")

    if on_status:
        on_status("A transcrever áudio (pode demorar alguns minutos)...")
    print("Modelo carregado!")
    print("\nA transcrever áudio...")
    print("Este processo pode demorar alguns minutos.\n")

    transcribe_kwargs: dict = {
        "task": "transcribe",
        "fp16": False,
        "verbose": True,
    }
    if idioma:
        transcribe_kwargs["language"] = idioma

    result = model.transcribe(caminho_audio, **transcribe_kwargs)
    texto = result["text"].strip()

    if not texto:
        raise RuntimeError("Não foi possível identificar fala no áudio.")

    print("\nA guardar ficheiro...")
    with open(saida, "w", encoding="utf-8") as f:
        f.write(texto)

    if not os.path.isfile(saida):
        raise RuntimeError("O ficheiro TXT não foi criado.")

    print("\n================================")
    print("TRANSCRIÇÃO CONCLUÍDA!")
    print("================================")
    print("Ficheiro:", saida)
    return saida


class TranscreverApp:
    """Interface gráfica para converter vídeo/YouTube e transcrever áudio."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Transcrever Áudio, Vídeo e YouTube")
        self.root.resizable(False, False)

        pasta_inicial = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.isdir(pasta_inicial):
            pasta_inicial = os.getcwd()

        self.var_origem = tk.StringVar(value="ficheiro")
        self.var_ficheiro = tk.StringVar()
        self.var_url = tk.StringVar()
        self.var_pasta_destino = tk.StringVar(value=pasta_inicial)
        self.var_formato = tk.StringVar(value="mp3")
        self.var_modelo = tk.StringVar(value="medium")
        self.var_idioma = tk.StringVar(value="Português (pt)")
        self.var_transcrever = tk.BooleanVar(value=True)
        self.var_converter_audio = tk.BooleanVar(value=False)
        self.var_status = tk.StringVar(value="Pronto para iniciar.")

        self._construir_interface()
        self._atualizar_campos_origem()

    def _construir_interface(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.grid(row=0, column=0, sticky="nsew")

        # Tipo de origem
        lf_origem = ttk.LabelFrame(container, text="1. Origem", padding=10)
        lf_origem.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        rb_frame = ttk.Frame(lf_origem)
        rb_frame.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Radiobutton(
            rb_frame,
            text="Ficheiro local (Áudio ou Vídeo)",
            variable=self.var_origem,
            value="ficheiro",
            command=self._atualizar_campos_origem,
        ).pack(side="left", padx=(0, 16))

        ttk.Radiobutton(
            rb_frame,
            text="Link do YouTube / Vídeo online",
            variable=self.var_origem,
            value="youtube",
            command=self._atualizar_campos_origem,
        ).pack(side="left")

        # Linha ficheiro local
        self.lbl_ficheiro = ttk.Label(lf_origem, text="Ficheiro:")
        self.lbl_ficheiro.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.ent_ficheiro = ttk.Entry(
            lf_origem, textvariable=self.var_ficheiro, width=52
        )
        self.ent_ficheiro.grid(row=1, column=1, sticky="ew", pady=4)
        self.btn_ficheiro = ttk.Button(
            lf_origem, text="Procurar...", command=self._selecionar_ficheiro
        )
        self.btn_ficheiro.grid(row=1, column=2, padx=(8, 0), pady=4)

        # Linha URL YouTube
        self.lbl_url = ttk.Label(lf_origem, text="Link URL:")
        self.lbl_url.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.ent_url = ttk.Entry(lf_origem, textvariable=self.var_url, width=52)
        self.ent_url.grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)

        # Linha Pasta destino (YouTube)
        self.lbl_pasta = ttk.Label(lf_origem, text="Guardar em:")
        self.lbl_pasta.grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.ent_pasta = ttk.Entry(
            lf_origem, textvariable=self.var_pasta_destino, width=52
        )
        self.ent_pasta.grid(row=3, column=1, sticky="ew", pady=4)
        self.btn_pasta = ttk.Button(
            lf_origem, text="Pasta...", command=self._selecionar_pasta
        )
        self.btn_pasta.grid(row=3, column=2, padx=(8, 0), pady=4)

        # Opções de conversão e transcrição
        lf_opcoes = ttk.LabelFrame(
            container, text="2. Conversão e Transcrição", padding=10
        )
        lf_opcoes.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(lf_opcoes, text="Formato ao converter vídeo/YouTube:").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=4
        )
        fmt_frame = ttk.Frame(lf_opcoes)
        fmt_frame.grid(row=0, column=1, sticky="w", pady=4)
        for fmt in OUTPUT_FORMATS:
            ttk.Radiobutton(
                fmt_frame,
                text=f".{fmt}",
                variable=self.var_formato,
                value=fmt,
            ).pack(side="left", padx=(0, 12))

        self.chk_converter_audio = ttk.Checkbutton(
            lf_opcoes,
            text="Converter também ficheiros de áudio para o formato selecionado",
            variable=self.var_converter_audio,
        )
        self.chk_converter_audio.grid(
            row=1, column=0, columnspan=2, sticky="w", pady=4
        )

        self.chk_transcrever = ttk.Checkbutton(
            lf_opcoes,
            text="Transcrever áudio para texto (.txt) com Whisper",
            variable=self.var_transcrever,
        )
        self.chk_transcrever.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)

        whisper_frame = ttk.Frame(lf_opcoes)
        whisper_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 2))

        ttk.Label(whisper_frame, text="Modelo:").pack(side="left", padx=(0, 6))
        self.cmb_modelo = ttk.Combobox(
            whisper_frame,
            textvariable=self.var_modelo,
            values=WHISPER_MODELS,
            state="readonly",
            width=10,
        )
        self.cmb_modelo.pack(side="left", padx=(0, 18))

        ttk.Label(whisper_frame, text="Idioma:").pack(side="left", padx=(0, 6))
        self.cmb_idioma = ttk.Combobox(
            whisper_frame,
            textvariable=self.var_idioma,
            values=list(LANGUAGE_OPTIONS.keys()),
            state="readonly",
            width=16,
        )
        self.cmb_idioma.pack(side="left")

        # Estado e ação
        self.progressbar = ttk.Progressbar(container, mode="indeterminate")
        self.progressbar.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        ttk.Label(container, textvariable=self.var_status).grid(
            row=3, column=0, sticky="w", pady=(0, 10)
        )

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=4, column=0, sticky="e")

        self.btn_iniciar = ttk.Button(
            btn_frame, text="Iniciar", command=self._iniciar_processamento
        )
        self.btn_iniciar.pack(side="right")

    def _atualizar_campos_origem(self) -> None:
        eh_ficheiro = self.var_origem.get() == "ficheiro"
        estado_ficheiro = "normal" if eh_ficheiro else "disabled"
        estado_youtube = "disabled" if eh_ficheiro else "normal"

        for widget in (self.ent_ficheiro, self.btn_ficheiro, self.chk_converter_audio):
            widget.configure(state=estado_ficheiro)

        for widget in (self.ent_url, self.ent_pasta, self.btn_pasta):
            widget.configure(state=estado_youtube)

    def _selecionar_ficheiro(self) -> None:
        audio_pats = " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))
        video_pats = " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
        ficheiro = filedialog.askopenfilename(
            title="Selecionar ficheiro de áudio ou vídeo",
            filetypes=[
                ("Áudio e Vídeo", f"{audio_pats} {video_pats}"),
                ("Áudio", audio_pats),
                ("Vídeo", video_pats),
                ("Todos os ficheiros", "*.*"),
            ],
        )
        if ficheiro:
            self.var_ficheiro.set(ficheiro)

    def _selecionar_pasta(self) -> None:
        pasta = filedialog.askdirectory(
            title="Selecionar pasta de destino",
            initialdir=self.var_pasta_destino.get() or os.getcwd(),
        )
        if pasta:
            self.var_pasta_destino.set(pasta)

    def _definir_ocupado(self, ocupado: bool) -> None:
        if ocupado:
            self.btn_iniciar.configure(state="disabled")
            self.progressbar.start(12)
        else:
            self.progressbar.stop()
            self.btn_iniciar.configure(state="normal")
            self._atualizar_campos_origem()

    def _atualizar_status(self, mensagem: str) -> None:
        self.root.after(0, lambda: self.var_status.set(mensagem))

    def _iniciar_processamento(self) -> None:
        tipo_origem = self.var_origem.get()
        origem = (
            self.var_ficheiro.get().strip()
            if tipo_origem == "ficheiro"
            else self.var_url.get().strip()
        )
        pasta_destino = self.var_pasta_destino.get().strip() or os.getcwd()
        formato = self.var_formato.get()
        modelo = self.var_modelo.get()
        idioma = LANGUAGE_OPTIONS.get(self.var_idioma.get(), "pt")
        fazer_transcricao = self.var_transcrever.get()
        converter_audio = self.var_converter_audio.get()

        if tipo_origem == "ficheiro" and not origem:
            messagebox.showwarning("Aviso", "Selecione um ficheiro de áudio ou vídeo.")
            return

        if tipo_origem == "youtube" and not origem:
            messagebox.showwarning("Aviso", "Introduza o link do YouTube ou vídeo.")
            return

        if tipo_origem == "ficheiro" and not fazer_transcricao:
            ext = os.path.splitext(origem)[1].lower()
            if ext in AUDIO_EXTENSIONS and not converter_audio:
                messagebox.showinfo(
                    "Aviso",
                    "Ative a transcrição ou a conversão de áudio para executar uma ação.",
                )
                return

        self._definir_ocupado(True)
        thread = threading.Thread(
            target=self._executar_tarefa,
            args=(
                origem,
                tipo_origem,
                formato,
                pasta_destino,
                modelo,
                idioma,
                fazer_transcricao,
                converter_audio,
            ),
            daemon=True,
        )
        thread.start()

    def _executar_tarefa(
        self,
        origem: str,
        tipo_origem: str,
        formato: str,
        pasta_destino: str,
        modelo: str,
        idioma: str | None,
        fazer_transcricao: bool,
        converter_audio: bool,
    ) -> None:
        try:
            if tipo_origem == "youtube":
                self._atualizar_status(
                    f"A descarregar e converter do YouTube para .{formato}..."
                )
            else:
                ext = os.path.splitext(origem)[1].lower()
                if ext not in AUDIO_EXTENSIONS or (
                    converter_audio and ext != f".{formato}"
                ):
                    self._atualizar_status(f"A converter ficheiro para .{formato}...")
                else:
                    self._atualizar_status("A preparar ficheiro de áudio...")

            caminho_audio, convertido = preparar_audio(
                origem=origem,
                tipo_origem=tipo_origem,
                formato_saida=formato,
                pasta_destino=pasta_destino,
                converter_audio=converter_audio,
            )

            caminho_txt = None
            if fazer_transcricao:
                caminho_txt = transcrever_audio(
                    caminho_audio=caminho_audio,
                    modelo=modelo,
                    idioma=idioma,
                    on_status=self._atualizar_status,
                )

            self._atualizar_status("Concluído com sucesso!")
            self.root.after(
                0,
                lambda a=caminho_audio, c=convertido, t=caminho_txt: self._mostrar_conclusao(
                    a, c, t
                ),
            )
        except Exception as erro:
            print("\nERRO NO PROCESSAMENTO:")
            traceback.print_exc()
            mensagem_erro = str(erro)
            self._atualizar_status("Ocorreu um erro.")
            self.root.after(
                0,
                lambda msg=mensagem_erro: messagebox.showerror(
                    "Erro", f"Ocorreu um erro:\n\n{msg}"
                ),
            )
        finally:
            self.root.after(0, lambda: self._definir_ocupado(False))

    def _mostrar_conclusao(
        self, caminho_audio: str, convertido: bool, caminho_txt: str | None
    ) -> None:
        partes = []
        if convertido:
            partes.append(f"Áudio guardado em:\n{caminho_audio}")
        if caminho_txt:
            partes.append(f"Transcrição guardada em:\n{caminho_txt}")

        messagebox.showinfo(
            "Processo concluído",
            "Operação concluída com sucesso!\n\n" + "\n\n".join(partes),
        )


def transcrever() -> None:
    root = tk.Tk()
    TranscreverApp(root)
    root.mainloop()


if __name__ == "__main__":
    transcrever()
