-- Iniciar/Encerrar turno: duas colunas novas em turnos_abertos (seguro rodar de novo)
alter table public.turnos_abertos
  add column if not exists hodometro_anterior numeric,
  add column if not exists piloto_nome text;
