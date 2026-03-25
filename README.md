# Projeto Tracker - Foundation v0.1

Projeto base do **Projeto Tracker**, focado em demonstrar uma arquitetura **AWS serverless** para simulação funcional de dispositivos IoT de rastreamento.

Nesta fundação inicial, o objetivo é provar o núcleo do simulador funcionando:

- persistência de estado do tracker no DynamoDB
- API HTTP no API Gateway
- processamento de comandos via Lambda
- seed inicial de trackers LT32 e LT32 PRO
- primeiros comandos simulados funcionando
- versionamento otimista para updates de estado
- logging estruturado mínimo com correlation_id
- testes unitários do núcleo

## Escopo desta versão

Esta versão **não** tenta reproduzir protocolo físico real, socket TCP, GT06, telemetria avançada ou painel operacional completo.

Ela entrega apenas o **núcleo mínimo executável**.

## Estrutura do repositório

```text
project-tracker/
├── backend/
│   ├── lambdas/
│   │   └── command_handler/
│   │       ├── app.py
│   │       ├── command_parser.py
│   │       ├── command_service.py
│   │       ├── config.py
│   │       ├── exceptions.py
│   │       ├── logging_utils.py
│   │       ├── repository.py
│   │       ├── responses.py
│   │       ├── utils.py
│   │       └── requirements.txt
│   ├── seeds/
│   │   ├── requirements.txt
│   │   └── seed_trackers.py
│   └── tests/
│       ├── requirements.txt
│       └── test_command_handler.py
├── docs/
│   └── MVP_FOUNDATION_V0.md
├── frontend/
│   └── README.md
├── infra/
│   └── terraform/
│       ├── api.tf
│       ├── dynamodb.tf
│       ├── iam.tf
│       ├── lambda.tf
│       ├── main.tf
│       ├── outputs.tf
│       ├── providers.tf
│       ├── terraform.tfvars.example
│       └── variables.tf
├── scripts/
│   └── test_commands.sh
├── .gitignore
└── README.md
```

## Pré-requisitos

- Terraform 1.6+
- AWS CLI configurado
- Python 3.11+
- credenciais AWS com permissão para criar Lambda, API Gateway, DynamoDB, IAM e CloudWatch Logs

## Passo a passo

### 0. Validar os testes locais

```bash
cd backend/tests
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

### 1. Ajustar variáveis do Terraform

Entre em `infra/terraform/` e copie o arquivo de exemplo:

```bash
cd ../../infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edite os valores se quiser mudar nomes, ambiente ou região.

### 2. Subir a infraestrutura

```bash
terraform init
terraform plan
terraform apply
```

Ao final, o Terraform vai retornar:

- URL da API
- nome da tabela DynamoDB
- nome da Lambda

### 3. Popular os trackers iniciais

Instale a dependência local do seed:

```bash
cd ../../backend/seeds
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Exporte a região e o nome da tabela gerados pelo Terraform:

```bash
export AWS_REGION=us-east-1
export TRACKER_TABLE_NAME=tracker-simulator-dev-trackers
```

Execute o seed:

```bash
python seed_trackers.py
```

### 4. Testar a API

Verifique saúde:

```bash
curl "https://SEU_API_ID.execute-api.us-east-1.amazonaws.com/health"
```

Enviar comando:

```bash
curl -X POST "https://SEU_API_ID.execute-api.us-east-1.amazonaws.com/command" \
  -H "Content-Type: application/json" \
  -d '{
    "tracker_id": "tracker-lt32-001",
    "command": "STATUS#"
  }'
```

### 5. Teste rápido via script

Na raiz do projeto:

```bash
chmod +x scripts/test_commands.sh
API_BASE_URL="https://SEU_API_ID.execute-api.us-east-1.amazonaws.com" ./scripts/test_commands.sh
```

## Comandos suportados nesta versão

- `STATUS#`
- `VERSION#`
- `PARAM#`
- `RELAY#`
- `RELAY,0#`
- `RELAY,1#`

## Melhorias técnicas já incorporadas

- parser simples com normalização de comando
- versionamento otimista com campo `version`
- tratamento explícito de conflito de concorrência (`409`)
- logging estruturado com `correlation_id`
- organização interna da Lambda por módulos
- testes unitários mínimos do núcleo

## Exemplo de resposta

```json
{
  "success": true,
  "tracker_id": "tracker-lt32-001",
  "model": "LT32",
  "command": "STATUS#",
  "response": "STATUS;POWER=EXTERNAL;IGN=OFF;GSM=REGISTERED;SIGNAL=18;BATTERY=4.08V;RELAY=OFF;LAT=-25.5043;LNG=-49.2905;ODOMETER_KM=15432.6",
  "state_snapshot": {
    "relay_state": 0,
    "version": 0
  }
}
```

## Próximos passos recomendados

Depois de validar esta base, a próxima camada correta é:

1. tabela de histórico/auditoria
2. EventBridge para simulação periódica
3. frontend mínimo de operação
4. motor simples de geração de eventos
5. autenticação básica para a API
