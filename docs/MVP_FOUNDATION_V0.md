# MVP Foundation v0.1

## Objetivo

Validar o núcleo mínimo executável do simulador funcional de trackers em AWS serverless.

## Critério de pronto

A Foundation v0.1 é considerada pronta quando os seguintes pontos estiverem validados:

1. Infra mínima criada com Terraform.
2. Tabela DynamoDB criada como fonte de verdade do estado do tracker.
3. Lambda `CommandHandler` implantada e acessível via API Gateway.
4. Seed inicial de trackers executado com sucesso.
5. Health check funcionando.
6. Comandos `STATUS#`, `VERSION#`, `PARAM#`, `RELAY#`, `RELAY,0#` e `RELAY,1#` funcionando ponta a ponta.
7. Updates de relay protegidos com versionamento otimista.
8. Logs estruturados mínimos no CloudWatch com `correlation_id`.
9. Testes unitários do núcleo executando localmente.

## Fora de escopo

- protocolo físico real
- GT06
- TCP socket
- autenticação robusta
- histórico persistente separado
- EventBridge
- dashboards
- frontend completo
- cenários de treino
- multitenancy
- GSI
- DynamoDB Streams

## Entregáveis desta fase

- estrutura inicial do repositório
- Terraform mínimo
- DynamoDB de trackers
- Lambda `CommandHandler`
- seed de trackers LT32 e LT32 PRO
- script de teste rápido
- testes unitários mínimos

## Motivo do recorte

Esta fase existe para provar o valor técnico central do projeto sem cair em overengineering. O foco é demonstrar modelagem de estado, processamento de comando, persistência e resposta coerente em arquitetura serverless.
