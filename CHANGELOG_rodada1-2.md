# Rodada 1-2 (v3.0-beta2) — o que mudou

## Segurança e proteção de dados
- Removido o "Acesso Rápido": não é mais possível abrir a conta de outra pessoa digitando a chave dela.
- Se a leitura da nuvem falhar, o app para com aviso e NÃO grava nada (antes podia sobrescrever
  o histórico com dados padrão). `load_state` agora devolve `(None, False)` na falha.
- `save_state` só grava com a nuvem confirmada e mostra o aviso na tela mesmo após o `st.rerun()`.
- Sem `state_key` na conta, o app não cai mais na conta compartilhada "beta_teste".

## Gravação segura entre sessões
- Novo `sincronizacao.py` (sem Streamlit): gravação com `version` (função SQL `salvar_state`) e
  mesclagem de 3 vias quando outra sessão gravou antes. Registros dos dois lados são preservados.
- Tabela de preços do gestor agora fica em `empresas.config_precos` (lida a cada execução).
  Autônomo continua usando `config_empresa` no próprio JSON.
- Moto ativa de gestor e piloto vale só para a sessão (não é mais gravada no JSON compartilhado).

## Correções
- Excluir turno: `int(sel_ex.split(" | ")[0])` (antes travava).
- Piloto sem moto atribuída vê aviso (antes via a primeira moto da empresa).
- ID de moto nova com uuid (antes podia colidir no mesmo dia).

## Novidades
- Backup em JSON na lateral (autônomo e gestor). Versão e ambiente no rodapé.
- 26 testes em `tests/` (cálculos, migração e sincronização):
  `python -m unittest discover -s tests -v`

## Ainda NÃO incluído (próximas rodadas)
- Convites com validade/revogação e bloqueio de tentativas de PIN (as colunas e tabelas já existem no banco).
- Botão Iniciar/Encerrar turno (tabela `turnos_abertos` já existe).
- Piloto ainda vê o valor_total da oficina na aba Garagem e o abastecimento do piloto ainda
  atualiza o preço da gasolina da moto.
