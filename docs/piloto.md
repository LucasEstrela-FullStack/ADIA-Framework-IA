# Roteiro do piloto

Como preparar uma máquina da escola, rodar uma coleta e encerrar o estudo. Tudo roda nessa
máquina; nenhum dado de estudante sai dela. Os comandos são do PowerShell, na raiz do
repositório.

## Antes de começar

- **Aprovação ética e consentimento.** O protótipo é o instrumento, não a autorização para
  usá-lo com pessoas (ver [`protocolo.md`](protocolo.md)).
- **BitLocker ligado** no disco da máquina. O banco `data/adia.db` e os backups guardam
  respostas de menores em texto puro; a cifragem do disco é a proteção contra perda ou roubo.
- **Decisões de pesquisa em aberto** (revisão de 2026-10-30): escopo da TAI na regra,
  base da confiança média (D9), contagem do DSS (D8), retorno de desempenho ao estudante
  (DO-41), condição C no piloto e número de itens da retenção (DO-43).

## Preparação, uma vez, com rede

```powershell
.\scripts\piloto.ps1 preparar
```

Instala as dependências pelos arquivos de bloqueio, constrói as telas e baixa
`qwen2.5:1.5b` e `bge-m3` no Ollama. Depois disso, nada mais precisa de rede.

Cadastre os participantes e guarde o vínculo código ↔ estudante só em `data/identidade/`,
que fica fora do banco e do git:

```powershell
uv run adia participantes criar --coorte turma-a --quantidade 30
```

## Dia da coleta

```powershell
.\scripts\piloto.ps1 verificar   # ambiente, guarda e Ollama de verdade
.\scripts\piloto.ps1 subir       # http://127.0.0.1:8000
```

Cada estudante abre `http://127.0.0.1:8000` e entra com o próprio código. A condição é
sorteada pelo servidor e não aparece na tela. Se a aba fechar, o mesmo código retoma do
ponto em que parou. Ao fim:

```powershell
.\scripts\piloto.ps1 backup      # cópia em data\backups\
.\scripts\piloto.ps1 parar
```

## Retenção, 7 a 9 dias depois

Suba de novo e peça a cada estudante para entrar com o mesmo código. Antes de 168 h a tela
diz quando volta; entre 168 e 216 h a última parte abre; depois de 216 h ela também abre,
mas fica marcada como fora de protocolo (DO-08, DO-43).

## Acompanhar e exportar

```powershell
uv run adia painel               # exportacoes\painel-<data>.html
uv run adia exportar             # exportacoes\<id>\eventos_*.csv e metricas_*.csv
uv run adia limiares             # mostra; com --opcao valor grava versão nova
```

O painel e os CSV ficam em `exportacoes/`, fora do git. O painel não passa pela API: o
estudante não tem como abri-lo.

## Encerramento

- `uv run adia excluir-dados --participante P-0001` apaga os dados de quem pedir, com
  registro.
- `uv run adia excluir-dados --expirados` aplica o prazo de 180 dias de DO-14. O prazo
  conta da conclusão da retenção.
- Ao fim do estudo, apague `data/backups/` e as cópias externas, e destrua o mapa de
  `data/identidade/` conforme a aprovação ética.
