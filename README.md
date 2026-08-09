---
title: Análise de Candidatos
emoji: ⚙️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Análise de Candidatos

Ferramenta para análise e ranqueamento de candidatos com base nos requisitos de uma vaga de emprego, utilizando IA via Hugging Face Inference API.

## Como usar

1. Insira os requisitos da vaga no campo de texto
2. Carregue os currículos dos candidatos no formato `.md`, `.pdf` ou `.docx`
3. Clique em **Analisar candidatos**

Os currículos podem ser `.md`, `.pdf` ou `.docx`. PDFs baseados em texto são convertidos diretamente para markdown; PDFs baseados em imagem (digitalizações) são lidos automaticamente via OCR e também convertidos para markdown. Arquivos `.docx` são convertidos para markdown preservando a estrutura (títulos, listas, ênfases) a partir dos estilos do Word. Todos são armazenados da mesma forma.

O formato legado `.doc` (Word 97-2003) **não** é suportado: por ser um binário OLE, ele exigiria um conversor externo como o LibreOffice. Salve o arquivo como `.docx` antes de carregá-lo. O mesmo vale para o `.odt` nativo do LibreOffice.

O resultado é um parecer executivo de RH com uma tabela ranqueando os candidatos por grau de alinhamento à vaga. O prompt enviado ao modelo fica disponível colapsado ao final da página para consulta ou uso manual.

## Executar localmente com Docker

```bash
docker build -t analise-candidatos .
docker run -p 7860:7860 -e HF_TOKEN=hf_... analise-candidatos
```

Para usar um modelo diferente do padrão (`meta-llama/Llama-3.3-70B-Instruct`):

```bash
docker run -p 7860:7860 -e HF_TOKEN=hf_... -e HF_MODEL=meta-llama/Llama-3.1-8B-Instruct analise-candidatos
```

Acesse em: http://localhost:7860

## Executar localmente sem Docker

```bash
pip install -r requirements.txt
# configure .streamlit/secrets.toml (veja secrets.toml.example)
python streamlit run app.py
```

Para a leitura de currículos baseados em imagem (OCR), é necessário ter o **Tesseract OCR** instalado no sistema, com o pacote de idioma português. No Docker isso já é feito automaticamente; localmente:

- **Windows:** instale a partir de https://github.com/UB-Mannheim/tesseract/wiki e, se necessário, defina a variável de ambiente `TESSERACT_CMD` com o caminho do executável (ex.: `C:\Program Files\Tesseract-OCR\tesseract.exe`).
- **Linux (Debian/Ubuntu):** `sudo apt-get install tesseract-ocr tesseract-ocr-por`
- **macOS:** `brew install tesseract tesseract-lang`

O idioma do OCR pode ser ajustado com a variável de ambiente `OCR_LANG` (padrão: `por`).

## Testes

A suíte de testes unitários cobre a configuração de segredos, a integração com a API do Hugging Face (incluindo o mapeamento de erros), a extração de currículos (texto, PDF de texto, PDF de imagem via OCR e `.docx`) e o carregamento da interface.

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes de OCR usam um `pytesseract` simulado, portanto **não** exigem o Tesseract instalado.

## Configuração de segredos (Hugging Face Spaces)

Em **Settings → Repository secrets**, adicione:

| Variável de ambiente | Valor |
|---|---|
| `HF_TOKEN` | Seu token da Hugging Face (com permissão de Inference) |
| `HF_MODEL` | Opcional. Ex: `meta-llama/Llama-3.3-70B-Instruct` |

O token pode ser criado em **huggingface.co → Settings → Access Tokens**.

O modelo escolhido precisa ser servido por algum Inference Provider habilitado na sua conta, em **Settings → Inference Providers**. Se nenhum provider habilitado servir o modelo, a API responde `model_not_supported`.

## Autor

| | |
|---|---|
| **Nome** | Rogério Mendes |
| **E-mail** | rogeriomendes@gmail.com |
| **GitHub** | https://github.com/rogeriomendesbr |
| **LinkedIn** | https://www.linkedin.com/in/rogeriomendesbr |
