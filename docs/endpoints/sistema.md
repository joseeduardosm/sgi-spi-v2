# Endpoints de sistema

Tag no OpenAPI: **Sistema**. Implementação: `backend/app/api/routes/saude.py`.

---

## `GET /api/saude`

Verifica se a API está respondendo. Usado por scripts de implantação, monitoramento e diagnóstico do Nginx.

- **Autorização:** pública.
- **Parâmetros:** nenhum.

### Resposta `200 OK`: `RespostaSaude`

| Campo | Tipo | Descrição |
|---|---|---|
| `situacao` | string | `ok` quando a API está no ar |
| `versao` | string | Versão da API |

```json
{ "situacao": "ok", "versao": "0.1.0" }
```

### Erros

| HTTP | Causa |
|---|---|
| `502 Bad Gateway` | Retornado pelo Nginx quando o serviço `contratos-spi-api` está parado |

```bash
curl http://<servidor>/api/saude
```
