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

## Ajuste 1 (após teste do piloto)
- Piloto não vê mais ganhos brutos (métrica e coluna do histórico), código de convite nem valores da oficina.
- Abastecimento e oficina do piloto não alteram preço da gasolina nem custo-base da peça.
- Turnos novos guardam piloto_email (registros antigos continuam filtrados pelo nome).

## Ainda NÃO incluído (próximas rodadas)
- Convites com validade/revogação e bloqueio de tentativas de PIN (as colunas e tabelas já existem no banco).
- Piloto ainda vê o valor_total da oficina na aba Garagem e o abastecimento do piloto ainda
  atualiza o preço da gasolina da moto.

## Rodada 4: Iniciar / Encerrar turno
- Rode ANTES do deploy: `sql/rodada4_turnos.sql` (2 colunas em `turnos_abertos`).
- Cartão "🏁 Turno" na aba Meu Turno: ▶️ Iniciar (grava hora e hodômetro no banco, sobrevive a fechar o app)
  e ⏹️ Encerrar (Km final, ganhos, extras) que gera o turno normal com início, fim e duração.
- Km entre o fim de um turno e o início do próximo = "fora de turno" (uso particular), calculado sozinho.
- Autônomo e gestor veem Líquido por hora, duração no histórico e km fora de turno. Piloto não vê valores.
- Gestor vê "🟢 Em turno agora" (quem, qual moto, desde que horas).
- Proteções: um turno aberto por pessoa, encerrar só vale uma vez (duplo clique/duas telas),
  falha ao salvar reabre o turno e recarrega da nuvem, alerta após 12 h aberto, cancelar turno.
- Novos: `turnos.py` (regras e banco, testável), `ui_turno.py` (tela), `tests/test_turnos.py`.
- Formulário manual de turno continua disponível (recolhido).

## Rodada 3: convites e login
- Convites com validade (1/7/30 dias), número de usos (1/5/10) e revogação, gerenciados pelo gestor
  em "👥 Convites para pilotos". Código aleatório de 8 caracteres (ex.: K7QM-4XPD), sem 0/O/1/I.
- O código antigo de `empresas.codigo_convite` NÃO entra mais. O gestor precisa gerar convites novos.
- Uso do convite é atômico (duas pessoas não usam o mesmo convite de uso único) e é devolvido se o cadastro falhar.
- PIN com PBKDF2 e sal aleatório por usuário. PINs antigos continuam valendo e são atualizados no primeiro login.
- Opcional: segredo `PIN_PEPPER` nos Secrets (defina uma vez e nunca troque).
- Bloqueio progressivo por conta: 5 erros seguidos = 15 min; a partir do 10º = 1 h; a partir do 15º = 24 h.
- Mensagem de login única ("E-mail ou PIN incorretos"), sem revelar se o e-mail existe.
- Cadastro exige PIN numérico de 4 a 6 dígitos com confirmação e valida o e-mail.
- Login não carrega mais o hash do PIN para a sessão.
- Novos: `seguranca.py`, `convites.py`, `ui_convites.py`, `tests/test_seguranca.py`, `tests/test_convites.py`.
