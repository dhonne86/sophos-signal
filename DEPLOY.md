# Publicacao com dominio proprio

Este app Streamlit ja esta pronto para ser publicado. Para usar um dominio proprio, publique o app em um provedor e depois aponte o DNS do dominio para a URL gerada pelo provedor.

## Opcao recomendada: Streamlit Community Cloud

1. Envie o projeto para um repositorio GitHub.
2. Crie um app no Streamlit Community Cloud usando `app.py` como arquivo principal.
3. Cadastre os secrets:

```toml
OPENAI_API_KEY = "sua_chave_openai"
BRAPI_API_KEY = "sua_chave_brapi"
```

4. O Streamlit vai gerar uma URL publica no formato:

```text
https://nome-do-app.streamlit.app
```

5. No painel DNS do seu dominio, crie um registro `CNAME` apontando seu subdominio para a URL do app.

Exemplo para `app.seudominio.com.br`:

```text
Tipo: CNAME
Nome: app
Valor: nome-do-app.streamlit.app
TTL: automatico
```

## Opcao com servidor proprio

Em uma VPS ou servidor cloud:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Depois configure um proxy reverso, como Nginx, para expor o app em HTTPS.

Exemplo de DNS:

```text
Tipo: A
Nome: app
Valor: IP_PUBLICO_DO_SERVIDOR
TTL: automatico
```

## Variaveis obrigatorias

Nunca coloque as chaves diretamente no codigo versionado.

```env
OPENAI_API_KEY=sua_chave_openai
BRAPI_API_KEY=sua_chave_brapi
```

## Checklist antes de publicar

- `requirements.txt` atualizado
- `app.py` na raiz do projeto
- `Diversos/ticker.csv` incluido no repositorio
- `OPENAI_API_KEY` configurada nos secrets
- `BRAPI_API_KEY` configurada nos secrets
- Pastas de saida ignoradas pelo Git
- Dominio comprado e DNS acessivel
