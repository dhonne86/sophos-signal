import polars as pl
import yfinance as yf
from pathlib import Path
from openai import OpenAI
import yaml
import os
import shutil
import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def obter_streamlit_secret(nome: str) -> str:
    """
    Le secrets do Streamlit quando o app estiver em deploy.
    """
    try:
        import streamlit as st

        return str(st.secrets.get(nome, "")).strip()
    except Exception:
        return ""

def carregar_config(path_yaml: str = "config.yaml") -> dict:
    """
    Função para carregar dados de configuração
    """
    caminho = Path(path_yaml)
    if not caminho.is_absolute():
        caminho = BASE_DIR / caminho
    with open(caminho, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = carregar_config()


def obter_openai_api_key() -> str:
    """
    Busca a chave da OpenAI em variavel de ambiente, .env ou config.yaml.
    """
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or obter_streamlit_secret("OPENAI_API_KEY")
        or config.get("openai_api_key", "")
    )
    return api_key.strip()


def obter_brapi_api_key() -> str:
    """
    Busca a chave da BRAPI em variavel de ambiente, .env ou config.yaml.
    """
    api_key = (
        os.getenv("BRAPI_API_KEY")
        or obter_streamlit_secret("BRAPI_API_KEY")
        or config.get("brapi_api_key", "")
    )
    return api_key.strip()


def criar_cliente_openai() -> OpenAI:
    api_key = obter_openai_api_key()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY nao configurada. Defina a variavel de ambiente "
            "ou configure o segredo no provedor de deploy."
        )
    return OpenAI(api_key=api_key)


def normalizar_ticker_brapi(ticker: str) -> str:
    """
    Converte tickers do Yahoo Finance, como PETR4.SA, para o formato da BRAPI.
    """
    return ticker.upper().replace(".SA", "").strip()


def buscar_cotacao_brapi(ticker: str) -> dict:
    """
    Busca cotacao atual na BRAPI para acoes, FIIs, ETFs e BDRs da B3.
    """
    token = obter_brapi_api_key()
    ticker_brapi = normalizar_ticker_brapi(ticker)
    params = urlencode({"fundamental": "true", "dividends": "false"})
    url = f"https://brapi.dev/api/quote/{ticker_brapi}?{params}"
    headers = {"User-Agent": "Sophos Streamlit"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        return {
            "erro": f"BRAPI retornou HTTP {e.code}.",
            "symbol": ticker_brapi,
        }
    except (URLError, TimeoutError) as e:
        return {
            "erro": f"Nao foi possivel conectar a BRAPI: {e}",
            "symbol": ticker_brapi,
        }
    except Exception as e:
        return {
            "erro": f"Erro inesperado ao consultar BRAPI: {e}",
            "symbol": ticker_brapi,
        }

    resultados = payload.get("results", [])
    if not resultados:
        return {
            "erro": "Nenhuma cotacao encontrada na BRAPI.",
            "symbol": ticker_brapi,
        }
    return resultados[0]


def img_b64(path: Path) -> str:
    '''
    Converte imagem em string codificada em base 64
    Formato necessário para Imagens para Modelos Multi-Modal
    '''
    return base64.b64encode(path.read_bytes()).decode()

def baixar_dados_b3(ticker: str, inicio: str, fim: str) -> pl.DataFrame:
    '''
    Função para baixar dados do b3, usando Yahoo Finance
    Salva na pasta LSTMOutput
    '''
    try:
        acao = yf.Ticker(ticker)
        dados = acao.history(start=inicio, end=fim)

        if dados.empty:
            print("Nenhum dado foi retornado para o período especificado.")
            return pl.DataFrame()

        dados.reset_index(inplace=True)
        dados = dados[["Date", "Open", "High", "Low", "Close", "Volume"]]
        dados_polars = pl.from_pandas(dados)

        output_dir = Path("LSTMOutput")
        output_dir.mkdir(parents=True, exist_ok=True)
        caminho_csv = output_dir / "dados.csv"
        dados_polars.write_csv(caminho_csv)

        print(f"Dados salvos com sucesso em: {caminho_csv}")
        return dados_polars

    except Exception as e:
        print(f"Erro ao baixar ou salvar dados: {e}")
        return pl.DataFrame()


def chamar_multimodal(prompt: str, img_b64_str: str, modelo: str) -> str:
    '''
    Função para Modelos Multi-Modal    
    '''
    resposta = criar_cliente_openai().chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64_str}"}
                    }
                ]
            }
        ],
        temperature=0.2,
        max_tokens=512
    )
    return resposta.choices[0].message.content.strip()

def chamar_textual(prompt: str, text: str, modelo: str) -> str:
    '''
    Função para Modelos 
    '''
    resposta = criar_cliente_openai().chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        temperature=0.3,
        max_tokens=512
    )
    return resposta.choices[0].message.content.strip()


def limpar_pastas(incluir_docs: bool = False):
    '''
    Limpa todos os dados gerados pela aplicação ao final da execução    
    '''
    pastas = ["LSTMOutput", "NoticiasOutput", "TecnicoOutput"]
    if incluir_docs:
        pastas.append("DocsAnaliseFund")
    for pasta in pastas:
        if os.path.exists(pasta):
            for nome_arquivo in os.listdir(pasta):
                caminho_arquivo = os.path.join(pasta, nome_arquivo)
                try:
                    if os.path.isfile(caminho_arquivo):
                        os.remove(caminho_arquivo)
                    elif os.path.isdir(caminho_arquivo):
                        shutil.rmtree(caminho_arquivo)
                except Exception as e:
                    print(f"Erro ao remover {caminho_arquivo}: {e}")
        else:
            print(f"Pasta não encontrada: {pasta}")


    

