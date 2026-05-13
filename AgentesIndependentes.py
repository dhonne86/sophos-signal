from pathlib import Path

import pandas as pd
import polars as pl

from Util import carregar_config, img_b64, chamar_multimodal, chamar_textual


config = carregar_config()


def analisar_previsao() -> str:
    imagem = img_b64(Path("LSTMOutput/previsao.png"))
    prompt = config["prompts"]["independentes"]["analisar_previsao"]
    modelo = config["modelos"]["independentes"]["analisar_previsao"]
    return chamar_multimodal(prompt, imagem, modelo)


def analisar_tecnico() -> str:
    imagem = img_b64(Path("TecnicoOutput/indicadores.png"))
    prompt = config["prompts"]["independentes"]["analisar_tecnico"]
    modelo = config["modelos"]["independentes"]["analisar_tecnico"]
    return chamar_multimodal(prompt, imagem, modelo)


def analisar_noticias() -> str:
    texto = Path("NoticiasOutput/noticias.txt").read_text(encoding="utf-8")[:4500]
    prompt = config["prompts"]["independentes"]["analisar_noticias"]
    modelo = config["modelos"]["independentes"]["analisar_noticias"]
    return chamar_textual(prompt, texto, modelo)


def _texto_tabela(df: pl.DataFrame, limite: int | None = None) -> str:
    trabalho = df.head(limite) if limite else df
    return trabalho.write_csv(separator="\t").strip()


def limpar_dataframe_financeiro(df: pl.DataFrame) -> pl.DataFrame:
    if not isinstance(df, pl.DataFrame):
        df = pl.from_pandas(df)
    df = df.rename({col: str(col).strip() for col in df.columns})
    if df.is_empty():
        return df
    df = df.filter(pl.any_horizontal(pl.all().is_not_null()))
    colunas_validas = [col for col in df.columns if df[col].null_count() < df.height]
    return df.select(colunas_validas)


def _normalizar_numero_expr(coluna: str) -> pl.Expr:
    return (
        pl.col(coluna)
        .cast(pl.Utf8, strict=False)
        .str.strip_chars()
        .str.replace_all(".", "", literal=True)
        .str.replace_all(",", ".", literal=True)
        .cast(pl.Float64, strict=False)
    )


def colunas_numericas(df: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    numericas = []
    trabalho = df
    for coluna in df.columns:
        nome = str(coluna).lower()
        if any(termo in nome for termo in ["codigo", "código", "descricao", "descrição", "precisao", "precisão"]):
            continue

        serie = trabalho.select(_normalizar_numero_expr(coluna).alias(coluna))[coluna]
        if serie.drop_nulls().len() > 0:
            trabalho = trabalho.with_columns(serie.alias(coluna))
            numericas.append(coluna)
    return trabalho, numericas


def identificar_coluna_conta(df: pl.DataFrame) -> str:
    candidatos = [
        "Descricao",
        "Descrição",
        "Descricao Conta",
        "Descrição Conta",
        "DS_CONTA",
        "Conta Contabil",
        "Conta Contábil",
        "Conta",
    ]
    for candidato in candidatos:
        if candidato in df.columns:
            return candidato
    return df.columns[0]


def ultimas_colunas_periodo(numericas: list[str], limite: int = 4) -> list[str]:
    return numericas[:limite] if len(numericas) > limite else numericas


def resumir_linhas_relevantes(df: pl.DataFrame, conta_col: str, periodo_cols: list[str], limite: int = 12) -> str:
    if not periodo_cols:
        return _texto_tabela(df, limite)

    ultimo_periodo = periodo_cols[0]
    trabalho = (
        df.select([conta_col] + periodo_cols)
        .with_columns(pl.col(ultimo_periodo).abs().alias("_abs_ultimo"))
        .sort("_abs_ultimo", descending=True)
        .head(limite)
        .drop("_abs_ultimo")
    )
    return _texto_tabela(trabalho)


def calcular_variacoes(df: pl.DataFrame, conta_col: str, periodo_cols: list[str], limite: int = 10) -> str:
    if len(periodo_cols) < 2:
        return "Sem periodos suficientes para calculo de variacao."

    ultimo, penultimo = periodo_cols[0], periodo_cols[1]
    trabalho = (
        df.select([conta_col, ultimo, penultimo])
        .with_columns(
            (pl.col(ultimo) - pl.col(penultimo)).alias("Variacao_abs"),
            pl.when(pl.col(penultimo) == 0).then(None).otherwise(pl.col(penultimo).abs()).alias("_denominador"),
        )
        .with_columns(((pl.col("Variacao_abs") / pl.col("_denominador")) * 100).alias("Variacao_pct"))
        .with_columns(pl.col("Variacao_abs").abs().alias("_score"))
        .sort("_score", descending=True)
        .head(limite)
        .drop(["_score", "_denominador"])
    )
    return _texto_tabela(trabalho)


def procurar_valor(df: pl.DataFrame, conta_col: str, periodo_col: str, termos: list[str]):
    contas = pl.col(conta_col).cast(pl.Utf8, strict=False).str.to_lowercase()
    for termo in termos:
        valores = (
            df.filter(contas.str.contains(termo.lower(), literal=True))
            .select(periodo_col)
            .drop_nulls()
        )
        if valores.height:
            return float(valores[periodo_col][0])
    return None


def calcular_indicadores_fundamentalistas(planilhas: dict[str, pl.DataFrame]) -> str:
    ativo = planilhas.get("DF Ind Ativo")
    passivo = planilhas.get("DF Ind Passivo")
    resultado = planilhas.get("DF Ind Resultado Periodo")
    fluxo = planilhas.get("DF Ind Fluxo de Caixa")
    linhas = []

    try:
        if ativo is not None and passivo is not None:
            ativo = limpar_dataframe_financeiro(ativo)
            passivo = limpar_dataframe_financeiro(passivo)
            ativo, ativo_nums = colunas_numericas(ativo)
            passivo, passivo_nums = colunas_numericas(passivo)
            ativo_conta = identificar_coluna_conta(ativo)
            passivo_conta = identificar_coluna_conta(passivo)
            periodo_ativo = ativo_nums[-1]
            periodo_passivo = passivo_nums[-1]

            ativo_total = procurar_valor(ativo, ativo_conta, periodo_ativo, ["ativo total", "total do ativo"])
            ativo_circulante = procurar_valor(ativo, ativo_conta, periodo_ativo, ["ativo circulante"])
            caixa = procurar_valor(ativo, ativo_conta, periodo_ativo, ["caixa", "equivalentes de caixa"])
            passivo_total = procurar_valor(passivo, passivo_conta, periodo_passivo, ["passivo total"])
            passivo_circulante = procurar_valor(passivo, passivo_conta, periodo_passivo, ["passivo circulante"])
            patrimonio = procurar_valor(passivo, passivo_conta, periodo_passivo, ["patrimonio liquido", "patrimônio líquido"])

            if ativo_circulante and passivo_circulante:
                linhas.append(f"Liquidez corrente aproximada: {ativo_circulante / passivo_circulante:.2f}")
            if passivo_total and patrimonio:
                linhas.append(f"Passivo / patrimonio liquido aproximado: {passivo_total / patrimonio:.2f}")
            if caixa and passivo_circulante:
                linhas.append(f"Caixa / passivo circulante aproximado: {caixa / passivo_circulante:.2f}")
            if patrimonio and ativo_total:
                linhas.append(f"Patrimonio liquido / ativo total aproximado: {patrimonio / ativo_total:.2f}")

        if resultado is not None:
            resultado = limpar_dataframe_financeiro(resultado)
            resultado, resultado_nums = colunas_numericas(resultado)
            resultado_conta = identificar_coluna_conta(resultado)
            periodo_resultado = resultado_nums[-1]
            receita = procurar_valor(resultado, resultado_conta, periodo_resultado, ["receita", "vendas"])
            lucro = procurar_valor(resultado, resultado_conta, periodo_resultado, ["lucro liquido", "lucro líquido"])
            ebit = procurar_valor(resultado, resultado_conta, periodo_resultado, ["resultado antes do resultado financeiro", "ebit"])

            if lucro is not None and receita:
                linhas.append(f"Margem liquida aproximada: {lucro / receita:.2%}")
            if ebit is not None and receita:
                linhas.append(f"Margem operacional aproximada: {ebit / receita:.2%}")

        if fluxo is not None:
            fluxo = limpar_dataframe_financeiro(fluxo)
            fluxo, fluxo_nums = colunas_numericas(fluxo)
            fluxo_conta = identificar_coluna_conta(fluxo)
            periodo_fluxo = fluxo_nums[-1]
            fco = procurar_valor(fluxo, fluxo_conta, periodo_fluxo, ["caixa liquido atividades operacionais", "atividades operacionais"])
            capex = procurar_valor(fluxo, fluxo_conta, periodo_fluxo, ["imobilizado", "intangivel", "investimento"])
            if fco is not None:
                linhas.append(f"Fluxo de caixa operacional aproximado: {fco:,.0f}")
            if fco is not None and capex is not None:
                linhas.append(f"FCO menos item de investimento/capex aproximado: {fco + capex:,.0f}")
    except Exception as e:
        linhas.append(f"Nao foi possivel calcular todos os indicadores derivados: {e}")

    return "\n".join(linhas) if linhas else "Indicadores derivados indisponiveis com a estrutura da planilha."


def montar_resumo_fundamentalista(planilhas: dict[str, pl.DataFrame]) -> str:
    abas_obrigatorias = [
        "DF Ind Ativo",
        "DF Ind Passivo",
        "DF Ind Resultado Periodo",
        "DF Ind Fluxo de Caixa",
        "DF Ind Valor Adicionado",
    ]

    partes = ["# Resumo fundamentalista estruturado"]
    partes.append("\n## Indicadores derivados\n")
    partes.append(calcular_indicadores_fundamentalistas(planilhas))

    for aba in abas_obrigatorias:
        if aba not in planilhas:
            partes.append(f"\n## {aba}\nAba nao encontrada.")
            continue

        df = limpar_dataframe_financeiro(planilhas[aba])
        if df.is_empty():
            partes.append(f"\n## {aba}\nAba vazia.")
            continue

        df, numericas = colunas_numericas(df)
        conta_col = identificar_coluna_conta(df)
        periodo_cols = ultimas_colunas_periodo(numericas)

        partes.append(f"\n## {aba}")
        partes.append(f"Linhas: {df.height} | Colunas: {len(df.columns)}")
        partes.append(f"Periodos analisados: {', '.join(periodo_cols) if periodo_cols else 'indisponivel'}")
        partes.append("\n### Contas mais relevantes por valor absoluto no ultimo periodo")
        partes.append(resumir_linhas_relevantes(df, conta_col, periodo_cols))
        partes.append("\n### Maiores variacoes entre os dois ultimos periodos")
        partes.append(calcular_variacoes(df, conta_col, periodo_cols))

    return "\n".join(partes)


def _read_excel_polars(caminho_excel: Path) -> dict[str, pl.DataFrame]:
    planilhas_pandas = pd.read_excel(caminho_excel, sheet_name=None)
    return {nome: pl.from_pandas(df) for nome, df in planilhas_pandas.items()}


def analisar_fundamentalista(doc: str) -> str:
    caminho_excel = Path(f"DocsAnaliseFund/{doc}")
    if not caminho_excel.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho_excel}")

    planilhas = _read_excel_polars(caminho_excel)
    resumo = montar_resumo_fundamentalista(planilhas)

    prompt = config["prompts"]["independentes"]["analisar_fundamentalista"]
    modelo = config["modelos"]["independentes"]["analisar_fundamentalista"]
    return chamar_textual(prompt, resumo[:12000], modelo)
