# -*- coding: utf-8 -*-
"""
Catálogo Nacional de Motocicletas e Custos Médios de Mercado
Raio-X do Entregador
"""

ESTABELECIMENTOS_LISTA = [
    "Nenhum (Apenas Apps)",
    "Sta. Efigênia",
    "Golden Sushi",
    "O Chef",
    "Particular",
    "Extra 1",
    "Extra 2"
]

CATALOGO_MOTOS = {
    "Honda NXR 150 Bros ESD 2008 (Carburada)": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 29.0,
        "seguro_anual": 984.08,
        "licenciamento_anual": 174.08,
        "projecao_anual_km": 37286.64,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 34.0},
            {"nome": "Limpeza/Regulagem Carburador", "intervalo": 12000, "custo": 120.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 70.0},
            {"nome": "Pastilha Freio Dianteiro (ESD)", "intervalo": 12000, "custo": 65.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 120.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 225.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 550.0},
            {"nome": "Bateria (Partida Elétrica)", "intervalo": 50000, "custo": 160.0}
        ]
    },
    "Honda CG 160 (Start / Fan / Titan)": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 38.0,
        "seguro_anual": 1350.00,
        "licenciamento_anual": 480.00,
        "projecao_anual_km": 40000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 42.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 65.0},
            {"nome": "Pastilha / Lona Freio Dianteiro", "intervalo": 12000, "custo": 60.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 55.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 18000, "custo": 195.0},
            {"nome": "Par de Pneus", "intervalo": 28000, "custo": 490.0},
            {"nome": "Bateria", "intervalo": 45000, "custo": 170.0}
        ]
    },
    "Honda CG 150 (Titan / Fan)": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 35.0,
        "seguro_anual": 1100.00,
        "licenciamento_anual": 280.00,
        "projecao_anual_km": 38000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 38.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 60.0},
            {"nome": "Freio Dianteiro", "intervalo": 12000, "custo": 55.0},
            {"nome": "Freio Traseiro", "intervalo": 15000, "custo": 50.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 18000, "custo": 175.0},
            {"nome": "Par de Pneus", "intervalo": 28000, "custo": 470.0},
            {"nome": "Bateria", "intervalo": 45000, "custo": 160.0}
        ]
    },
    "Honda Pop 110i / Biz 110i-125": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 46.0,
        "seguro_anual": 850.00,
        "licenciamento_anual": 320.00,
        "projecao_anual_km": 35000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 35.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 55.0},
            {"nome": "Lonas de Freio (Diant + Tras)", "intervalo": 14000, "custo": 85.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 16000, "custo": 145.0},
            {"nome": "Par de Pneus", "intervalo": 25000, "custo": 390.0},
            {"nome": "Bateria", "intervalo": 45000, "custo": 150.0}
        ]
    },
    "Mottu Sport 110i / TVS (Própria)": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 48.0,
        "seguro_anual": 800.00,
        "licenciamento_anual": 290.00,
        "projecao_anual_km": 40000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 35.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 55.0},
            {"nome": "Freios (Diant + Tras)", "intervalo": 14000, "custo": 85.0},
            {"nome": "Kit Relação", "intervalo": 16000, "custo": 150.0},
            {"nome": "Par de Pneus", "intervalo": 25000, "custo": 380.0}
        ]
    },
    "Yamaha Factor 150 / Fazer 150": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 39.0,
        "seguro_anual": 1280.00,
        "licenciamento_anual": 460.00,
        "projecao_anual_km": 40000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 44.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 70.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 60.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 18000, "custo": 210.0},
            {"nome": "Par de Pneus", "intervalo": 28000, "custo": 500.0},
            {"nome": "Bateria", "intervalo": 45000, "custo": 180.0}
        ]
    },
    "Honda NXR 160 Bros / Yamaha Crosser 150": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 34.0,
        "seguro_anual": 1450.00,
        "licenciamento_anual": 520.00,
        "projecao_anual_km": 40000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 42.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 75.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Pastilha/Lona Freio Traseiro", "intervalo": 14000, "custo": 65.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 240.0},
            {"nome": "Par de Pneus (Uso Misto)", "intervalo": 30000, "custo": 580.0},
            {"nome": "Bateria", "intervalo": 45000, "custo": 180.0}
        ]
    },
    "Yamaha Fazer 250 / Lander 250 / CB Twister": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 28.0,
        "seguro_anual": 1850.00,
        "licenciamento_anual": 650.00,
        "projecao_anual_km": 40000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo + Filtro", "intervalo": 2500, "custo": 75.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 95.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 85.0},
            {"nome": "Pastilha Freio Traseiro", "intervalo": 12000, "custo": 80.0},
            {"nome": "Kit Relação (Com Retentor)", "intervalo": 22000, "custo": 340.0},
            {"nome": "Par de Pneus (Radiais/Largos)", "intervalo": 25000, "custo": 850.0},
            {"nome": "Bateria", "intervalo": 45000, "custo": 220.0}
        ]
    },
    "Moto Alugada (Mottu / Locadora - Manutenção Inclusa)": {
        "tipo": "alugada",
        "preco_gasolina": 5.99,
        "consumo_kml": 45.0,
        "seguro_anual": 0.0,
        "licenciamento_anual": 0.0,
        "projecao_anual_km": 40000.0,
        "aluguel_semanal": 250.0,
        "pecas": []
    },
    "Personalizada (Preencher Manualmente)": {
        "tipo": "propria",
        "preco_gasolina": 5.99,
        "consumo_kml": 35.0,
        "seguro_anual": 1000.00,
        "licenciamento_anual": 300.00,
        "projecao_anual_km": 36000.0,
        "aluguel_semanal": 0.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 40.0},
            {"nome": "Freios (Diant + Tras)", "intervalo": 12000, "custo": 110.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 18000, "custo": 200.0},
            {"nome": "Par de Pneus", "intervalo": 28000, "custo": 500.0}
        ]
    }
}

def criar_moto_do_catalogo(moto_id: str, apelido: str, modelo_catalogo: str, hodometro_inicial: int) -> dict:
    base = CATALOGO_MOTOS.get(modelo_catalogo, CATALOGO_MOTOS["Personalizada (Preencher Manualmente)"])
    pecas_clonadas = [
        {
            "nome": p["nome"],
            "intervalo": p["intervalo"],
            "ultima_km": hodometro_inicial,
            "custo": p["custo"]
        }
        for p in base["pecas"]
    ]
    return {
        "id": moto_id,
        "apelido": apelido,
        "modelo": modelo_catalogo,
        "tipo": base.get("tipo", "propria"),
        "hodometro": hodometro_inicial,
        "preco_gasolina": base["preco_gasolina"],
        "consumo_kml": base["consumo_kml"],
        "seguro_anual": base["seguro_anual"],
        "licenciamento_anual": base["licenciamento_anual"],
        "projecao_anual_km": base["projecao_anual_km"],
        "aluguel_semanal": base.get("aluguel_semanal", 0.0),
        "pecas": pecas_clonadas
    }
