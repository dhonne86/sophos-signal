from pathlib import Path

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException

from Util import carregar_config

config = carregar_config()


def fonte_permitida(link: str, fontes: list[str]) -> bool:
    if not fontes:
        return True
    return any(fonte.lower() in link.lower() for fonte in fontes)


def adicionar_noticia(noticias: list[dict], vistos: set[str], secao: str, resultado: dict):
    link = resultado.get("url", "")
    if not link or link in vistos:
        return

    noticias.append(
        {
            "secao": secao,
            "titulo": resultado.get("title", "Sem titulo"),
            "corpo": resultado.get("body", ""),
            "link": link,
            "data": resultado.get("date", ""),
            "fonte": resultado.get("source", ""),
        }
    )
    vistos.add(link)


def buscar_por_consultas(ddgs, consultas: list[str], secao: str, fontes: list[str], limite: int):
    noticias = []
    vistos = set()

    for query in consultas:
        resultados = ddgs.news(
            keywords=query,
            region="br-pt",
            max_results=limite,
        )
        for resultado in resultados:
            link = resultado.get("url", "")
            if fonte_permitida(link, fontes):
                adicionar_noticia(noticias, vistos, secao, resultado)
            if len(noticias) >= limite:
                break
        if len(noticias) >= limite:
            break

    return noticias


def montar_consultas_empresa(empresa: str, termos: list[str]) -> list[str]:
    return [f"{empresa} {termo}" for termo in termos]


def escrever_noticias(arquivo: Path, empresa: str, noticias: list[dict], erro_busca):
    secoes = [
        ("Empresa selecionada", "Noticias da empresa"),
        ("IBOVESPA e B3", "Noticias nacionais relacionadas ao IBOVESPA"),
        ("Cenario macroeconomico", "Cenarios economicos nacionais e internacionais"),
    ]

    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(f"Resumo de noticias financeiras para analise de {empresa}\n\n")

        if noticias:
            for secao_id, titulo_secao in secoes:
                itens = [noticia for noticia in noticias if noticia["secao"] == secao_id]
                if not itens:
                    continue

                f.write(f"## {titulo_secao}\n\n")
                for i, noticia in enumerate(itens, 1):
                    f.write(f"{i}. {noticia['titulo']}\n")
                    if noticia["fonte"]:
                        f.write(f"Fonte: {noticia['fonte']}\n")
                    if noticia["data"]:
                        f.write(f"Data: {noticia['data']}\n")
                    if noticia["corpo"]:
                        f.write(f"{noticia['corpo']}\n")
                    f.write(f"Link: {noticia['link']}\n\n")
            return

        if erro_busca:
            f.write(
                "Nao foi possivel buscar noticias financeiras neste momento. "
                "O DuckDuckGo retornou limite de acesso ou erro temporario.\n"
            )
            f.write(f"Detalhe tecnico: {erro_busca}\n")
        else:
            f.write("Nenhuma noticia financeira encontrada para os canais configurados.\n")


def buscar_noticias_financeiras_ddg(empresa: str):
    """
    Busca noticias da empresa, do IBOVESPA/B3 e de cenarios macroeconomicos.
    Se o DuckDuckGo aplicar rate limit, salva um aviso e permite o app continuar.
    """
    noticias_config = config["noticias"]
    termos_empresa = noticias_config.get("termos", [])
    termos_ibovespa = noticias_config.get("termos_ibovespa", [])
    cenarios_economicos = noticias_config.get("cenarios_economicos", [])
    fontes = noticias_config.get("fontes", [])
    max_por_secao = noticias_config.get("maximo_por_secao", 4)

    output_dir = Path("NoticiasOutput")
    output_dir.mkdir(exist_ok=True)
    arquivo = output_dir / "noticias.txt"

    ddgs = DDGS()
    noticias = []
    erro_busca = None

    consultas = [
        (
            "Empresa selecionada",
            montar_consultas_empresa(empresa, termos_empresa),
        ),
        (
            "IBOVESPA e B3",
            termos_ibovespa,
        ),
        (
            "Cenario macroeconomico",
            cenarios_economicos,
        ),
    ]

    try:
        for secao, queries in consultas:
            noticias.extend(
                buscar_por_consultas(
                    ddgs=ddgs,
                    consultas=queries,
                    secao=secao,
                    fontes=fontes,
                    limite=max_por_secao,
                )
            )
    except DuckDuckGoSearchException as e:
        erro_busca = e

    escrever_noticias(arquivo, empresa, noticias, erro_busca)
    print(f"{len(noticias)} noticias salvas em: {arquivo}")
