# Sophos Signal

MVP SaaS em Streamlit para sinais educacionais de daytrade na B3, com radar tecnico, entrada, stop, alvo, score de confianca, historico da sessao e envio diario por e-mail. O modulo de research com LSTM, noticias e agentes OpenAI segue disponivel como camada complementar.

## Recursos

- MVP de sinais com janela tecnica padrao dos ultimos 90 dias
- Processamento de CSVs, indicadores e sinais com Polars
- Setup operacional com direcao, entrada, stop, alvo e risco/retorno
- Watchlist, planos simulados e historico de sinais
- Interface mobile responsiva com manifest PWA para instalar na tela inicial
- Pagina HTML diaria gerada por `daily_signal_email.py`
- Envio diario por SMTP para `dhonne137@gmail.com` quando o `.env` estiver configurado
- Selecao de empresas a partir de `Diversos/ticker.csv`
- Cotacao atual da B3 via BRAPI
- Download de dados historicos via Yahoo Finance
- Previsao de precos com LSTM
- Indicadores tecnicos: RSI, MACD, medias moveis, VWAP, ATR, ADX, Estocastico e Bollinger
- Busca de noticias financeiras com tolerancia a rate limit
- Canais nacionais e internacionais para IBOVESPA, B3 e cenarios macroeconomicos
- Analise por agentes independentes e avaliadores finais
- Upload opcional de planilha Excel para analise fundamentalista

## Execucao local

1. Crie e ative um ambiente virtual:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Configure as chaves:

```powershell
Copy-Item .env.example .env
```

Edite `.env` e preencha:

```env
OPENAI_API_KEY=sua_chave
BRAPI_API_KEY=sua_chave_brapi
```

Para envio de e-mail, configure tambem as variaveis SMTP na secao abaixo.

4. Execute:

```powershell
streamlit run app.py
```

O app ficara disponivel em `http://localhost:8501`.

## Uso no celular

1. Execute o app localmente ou em deploy HTTPS.
2. Abra o endereco pelo navegador do celular.
3. Use a opcao do navegador para adicionar o Sophos Signal a tela inicial.

Os arquivos PWA ficam em `static/` e sao servidos pelo Streamlit com
`enableStaticServing = true` em `.streamlit/config.toml`.

Se o Android estiver conectado por USB com Depuracao USB autorizada, abra o
app direto no aparelho:

```powershell
.\open_android.ps1
```

## Envio diario por e-mail

O projeto inclui o script `daily_signal_email.py`, que gera `daily_signal_page.html`
com o sinal operacional dos ultimos 90 dias e envia o HTML para o e-mail configurado.

Configure no `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app
SMTP_FROM=seu_email@gmail.com
SIGNAL_EMAIL_TO=dhonne137@gmail.com
SIGNAL_TICKER=PETR4.SA
SIGNAL_EMPRESA=PETROBRAS
SIGNAL_WINDOW_DAYS=90
```

Teste sem enviar:

```powershell
.\venv\Scripts\python.exe daily_signal_email.py --dry-run
```

Envie manualmente:

```powershell
.\venv\Scripts\python.exe daily_signal_email.py --recipient dhonne137@gmail.com
```

## Deploy no Streamlit Community Cloud

1. Envie este projeto para um repositorio GitHub.
2. No Streamlit Community Cloud, crie um novo app apontando para `app.py`.
3. Em `Settings > Secrets`, adicione:

```toml
OPENAI_API_KEY = "sua_chave"
BRAPI_API_KEY = "sua_chave_brapi"
```

4. Confirme que `requirements.txt`, `config.yaml`, `Diversos/ticker.csv` e os arquivos `.py` estao no repositorio.

## Deploy no Render

O arquivo `render.yaml` ja prepara o app como Web Service.

### Comando de inicializacao

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

### Secrets no Render

```env
OPENAI_API_KEY
BRAPI_API_KEY
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_FROM
SIGNAL_EMAIL_TO
SIGNAL_TICKER
SIGNAL_EMPRESA
SIGNAL_WINDOW_DAYS
```

## Observacoes

- Nao versionar `.env` nem `.streamlit/secrets.toml`.
- A cotacao atual usa a BRAPI. O token deve ficar em `BRAPI_API_KEY`, nunca direto no codigo.
- A busca de noticias pode retornar rate limit do DuckDuckGo; nesse caso, o app continua a analise e registra o aviso em `NoticiasOutput/noticias.txt`.
- TensorFlow pode deixar o deploy mais pesado. Se o provedor tiver pouca memoria, reduza epocas/camadas do modelo LSTM ou use um modelo salvo.
- Referencia de pesquisa adicionada: [indicadores tecnicos para daytrade avancados](https://www.google.com/search?q=indicadores+t%C3%A9cnicos+para+daytrade+avancados&gs_lcrp=EgZjaHJvbWUyBggAEEUYOTIJCAEQIRgKGKABMgkIAhAhGAoYoAHSAQkxNjczMWowajeoAgCwAgA&sourceid=chrome&ie=UTF-8&udm=50&fbs=ADc_l-acAb_3MMOAUx0zmbUpgBqRiigBgL2I_pgQa-94zvB054Dys3s2x_Qm_GJcU2DlSXgs4i471_5vbbrE24Q_ZqrCatB7YnmDqpjaDf_BPVQIphT8Z0Z9fcDPiwTYfwrWWu5shwYfSZKhWFt_TtDEQlDoNShgltfuX8QU5u_gJAbSDrk9fKszywWWTY4JdC22JK2hgSQoTo4ObBF2_fwqzwHykRvWTw&ved=2ahUKEwi_4uXUxLaUAxVnrJUCHWWUGQAQ0NsOegQIAxAB&aep=10&ntc=1&ccb=1&cs=0&hl=pt-PT&biw=1536&bih=695.2000122070312&mstk=AUtExfDKsdlVHGlyHN8OfH4YtITOsUmo021NbVmvSAD3e7oTXhNn0j9k6ufYn2MWxFhLxGkeqzWk7_xJjUajOnSD06K0fTkulH9KH6TB-524d_SZ8CeQkX034R1gFt1IX73WQ4N-bgCWByzzGdCOfGPtJYE3S9LLlEO1npY&csuir=1&mtid=CZMEapihHvb95OUP5ueuWQ).
