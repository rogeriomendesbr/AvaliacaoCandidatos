import streamlit as st
import pymupdf
import pymupdf4llm
from pathlib import Path
from services.llm import analyze_resumes, build_prompt, RateLimitError, AuthenticationError, APIError, TokenLimitError, PromptInjectionError
from services.config import get_groq_api_key, get_groq_model
from services.extract import extract_resume, OCRError, UnsupportedFormatError

st.set_page_config(
    page_title="Avaliação de Candidatos",
    page_icon="assets/logo.png",
    layout="wide",
)


@st.cache_data
def load_css() -> str:
    return Path("assets/style.css").read_text(encoding="utf-8")


@st.cache_data
def load_prompt_template() -> str:
    return Path("prompts/analysis.md").read_text(encoding="utf-8")


TOKEN_LIMIT_MESSAGE = (
    "📄 O conteúdo enviado excede o limite de tokens do modelo.\n\n"
    "Tente reduzir o número de currículos analisados por vez ou encurtar os requisitos da vaga."
)

PROMPT_INJECTION_MESSAGE = (
    "🛑 Foi identificado conteúdo suspeito em um dos currículos enviados (possível tentativa de manipular a avaliação da IA).\n\n"
    "Remova ou revise o arquivo suspeito e tente novamente."
)


if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "requisites_key" not in st.session_state:
    st.session_state.requisites_key = 0

if "pending_upload" not in st.session_state:
    st.session_state.pending_upload = None

if "upload_error" not in st.session_state:
    st.session_state.upload_error = None

if "analyzing" not in st.session_state:
    st.session_state.analyzing = False

if "analysis_message" not in st.session_state:
    st.session_state.analysis_message = None

# Upload e avaliação se excluem mutuamente: enquanto um currículo está sendo
# processado, o botão de avaliação fica desabilitado, e vice-versa — evita
# que as duas operações concorram (ex.: iniciar uma avaliação enquanto um
# currículo ainda não terminou de ser convertido para markdown).
upload_processing = st.session_state.pending_upload is not None
busy = upload_processing or st.session_state.analyzing

# Um único bloco de estilo, sempre presente (nunca inserido/removido
# condicionalmente): alternar a presença de um elemento <style> desloca
# tudo abaixo dele na página, já que cada st.markdown ocupa seu próprio
# espaço no fluxo. Só o conteúdo do cursor varia conforme `busy`.
cursor_rule = "* { cursor: wait !important; }" if busy else ""
st.markdown(f"<style>{load_css()}\n{cursor_rule}</style>", unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 20], vertical_alignment="center")
with col_logo:
    st.image("assets/logo.png", width=64)
with col_title:
    st.subheader("Avaliação de Candidatos")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f'<label class="top-label">Insira os requisitos da vaga:</label>', unsafe_allow_html=True)
    text_requisites = st.text_area(
        "Requisitos da vaga",
        height=200,
        key=f"requisites_{st.session_state.requisites_key}",
        label_visibility="collapsed",
        placeholder=(
            "Descrição da vaga:\n"
            "-\n"
            "\n"
            "Requisitos obrigatórios:\n"
            "-\n"
            "\n"
            "Requisitos desejáveis:\n"
            "-"
        ),
    )

with col2:
    st.markdown(f'<label class="top-label">Escolha os currículos no formato .txt, .md, .docx ou .pdf:</label>', unsafe_allow_html=True)

    # Altura fixa, igual à de col3: sem isso, o spinner e a mensagem de erro
    # abaixo do uploader mudam a altura desta coluna conforme o estado,
    # empurrando o divisor/botão/resultado abaixo para cima e para baixo.
    with st.container(height=154, border=False):
        # Sem `type=[...]`: essa restrição é aplicada pelo Streamlit antes do
        # nosso código rodar e uma extensão inválida derruba o app com uma
        # exceção que não pode ser capturada. A validação real acontece em
        # extract_resume(), cujos erros já tratamos de forma amigável abaixo.
        uploaded_file = st.file_uploader(
            "Currículos dos candidatos",
            key=f"uploader_{st.session_state.uploader_key}",
            label_visibility="collapsed",
            disabled=busy,
        )

        if uploaded_file is not None and not busy:
            # Guarda os bytes e refaz o rerun antes de processar, para que o
            # widget apareça desabilitado no próximo run enquanto extract_resume()
            # (que pode envolver OCR e demorar) roda.
            st.session_state.pending_upload = {"name": uploaded_file.name, "bytes": uploaded_file.read()}
            st.session_state.upload_error = None
            st.rerun()

        if upload_processing:
            pending = st.session_state.pending_upload
            with st.spinner("Processando currículo..."):
                try:
                    content = extract_resume(pending["name"], pending["bytes"])
                except (OCRError, UnsupportedFormatError) as e:
                    st.session_state.upload_error = f"⚠️ {e}"
                except Exception as e:
                    st.session_state.upload_error = f"Não foi possível processar o arquivo: {e}"
                else:
                    st.session_state.uploaded_files[pending["name"]] = content
                finally:
                    # A mensagem de erro (se houver) só é exibida no próximo run:
                    # st.rerun() encerra este run imediatamente, e um st.error()
                    # chamado bem antes dele nunca chega a ser visto pelo usuário
                    # — a página já é substituída pelo run seguinte antes de renderizar.
                    st.session_state.pending_upload = None
                    st.session_state.uploader_key += 1
                    st.rerun()

        if st.session_state.upload_error:
            st.error(st.session_state.upload_error)
            st.session_state.upload_error = None

with col3:
    st.markdown(f'<label class="top-label">Currículos carregados:</label>', unsafe_allow_html=True)
    with st.container(height=154, border=False):
        if st.session_state.uploaded_files:
            to_remove = st.pills(
                "Selecione para remover:",
                options=list(st.session_state.uploaded_files.keys()),
                format_func=lambda name: f"{name}  ✕",
                selection_mode="multi",
                label_visibility="collapsed",
            )
            if to_remove:
                for name in to_remove:
                    del st.session_state.uploaded_files[name]
                st.rerun()
        else:
            st.caption("Nenhum currículo carregado.")

st.divider()

col_go, col_clear = st.columns(2)
with col_go:
    clicked = st.button("Avaliar candidatos", key="go-button", disabled=busy)
with col_clear:
    clear_clicked = st.button("Limpar dados", key="clear-button", disabled=busy)

if clear_clicked and not busy:
    # Reinicia o app: limpa currículos, requisitos e qualquer resultado ou
    # mensagem pendente. Os widgets de texto/upload são recriados do zero
    # via troca de key, que é a forma correta de "limpar" um widget do
    # Streamlit (não dá para simplesmente atribuir um novo valor a eles).
    st.session_state.uploaded_files = {}
    st.session_state.uploader_key += 1
    st.session_state.requisites_key += 1
    st.session_state.pending_upload = None
    st.session_state.upload_error = None
    st.session_state.analyzing = False
    st.session_state.analysis_message = None
    st.rerun()

if clicked and not busy:
    # Mesmo padrão do upload: refaz o rerun antes de processar, para que o
    # botão apareça desabilitado no próximo run enquanto a avaliação (que
    # envolve uma chamada de rede à API da Groq) roda.
    st.session_state.analyzing = True
    st.session_state.analysis_message = None
    st.rerun()

if st.session_state.analyzing:
    with st.spinner("Analisando..."):
        if not text_requisites or not st.session_state.uploaded_files:
            st.session_state.analysis_message = {
                "type": "error",
                "text": "Por favor, insira os requisitos da vaga e carregue pelo menos um currículo.",
            }
        else:
            api_key = get_groq_api_key()

            if not api_key:
                st.session_state.analysis_message = {
                    "type": "error",
                    "text": "⚠️ Nenhuma API key da Groq configurada. Configure a variável de ambiente GROQ_API_KEY para executar a avaliação.",
                }
            else:
                prompt_template = load_prompt_template()
                try:
                    user_prompt = build_prompt(prompt_template, text_requisites, st.session_state.uploaded_files)
                except TokenLimitError:
                    st.session_state.analysis_message = {"type": "error", "text": TOKEN_LIMIT_MESSAGE}
                except PromptInjectionError:
                    st.session_state.analysis_message = {"type": "error", "text": PROMPT_INJECTION_MESSAGE}
                else:
                    try:
                        result = analyze_resumes(
                            api_key=api_key,
                            model=get_groq_model(),
                            prompt=user_prompt,
                        )
                        st.session_state.analysis_message = {
                            "type": "success",
                            "text": "Avaliação concluída com sucesso!",
                            "result": result,
                            "prompt": user_prompt,
                        }
                    except TokenLimitError:
                        st.session_state.analysis_message = {"type": "error", "text": TOKEN_LIMIT_MESSAGE}
                    except RateLimitError:
                        st.session_state.analysis_message = {
                            "type": "error",
                            "text": "Limite de uso atingido no Groq.com. Tente novamente em alguns minutos",
                        }
                    except AuthenticationError:
                        st.session_state.analysis_message = {
                            "type": "error",
                            "text": "❌ Erro de autenticação: a sua API key da Groq é inválida ou foi revogada.",
                        }
                    except APIError as e:
                        st.session_state.analysis_message = {
                            "type": "error",
                            "text": f"💥 Ocorreu um erro na API da Groq: {e.message}",
                        }
                    except Exception as e:
                        st.session_state.analysis_message = {
                            "type": "error",
                            "text": f"Anomalia inesperada: {e}",
                        }

        # Mesma razão do upload: st.error()/st.success() chamado agora nunca
        # seria visto, pois o st.rerun() logo abaixo substitui a página
        # antes do navegador conseguir renderizá-lo. A mensagem guardada em
        # session_state é exibida no próximo run (já com o botão reabilitado).
        st.session_state.analyzing = False
        st.rerun()

if st.session_state.analysis_message:
    msg = st.session_state.analysis_message
    if msg["type"] == "success":
        st.success(msg["text"])
        st.write(msg["result"])
        with st.expander("Prompt enviado ao modelo"):
            st.code(msg["prompt"], language="markdown")
    else:
        st.error(msg["text"])
    st.session_state.analysis_message = None
