import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DE TELA E RESPONSIVIDADE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SGP - Gestão Pedagógica",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilização CSS unificada para TV (Dark Mode) e Celular (Responsivo)
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        
        /* Cards do Painel BI (TV) */
        .metric-card {
            background-color: #0d121f;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .metric-value {
            font-size: 24pt;
            font-weight: bold;
            color: #10b981;
            margin-bottom: 2px;
        }
        .metric-label {
            font-size: 9pt;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Badges de Status (Tabela da TV) */
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 8.5pt;
            font-weight: bold;
            display: inline-block;
            text-align: center;
        }
        .badge-now { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
        .badge-prev { background-color: #1e293b; color: #94a3b8; }
        .badge-next { background-color: #1e3a8a; color: #60a5fa; border: 1px solid #2563eb; }
        
        /* Cards de Linha do Tempo Vertical (Mobile) */
        .mobile-card {
            background-color: #1e293b;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 12px;
            border-left: 5px solid #64748b;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }
        .mobile-card-active {
            background-color: #0f172a;
            border-left: 5px solid #10b981;
            border-top: 1px solid #059669;
            border-bottom: 1px solid #059669;
            border-right: 1px solid #059669;
        }
        .mobile-card-next {
            border-left: 5px solid #3b82f6;
        }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CONEXÃO COM O GOOGLE SHEETS
# -----------------------------------------------------------------------------
@st.cache_resource
def conectar_google_sheets():
    caminho_credenciais = "credenciais.json"
    if not os.path.exists(caminho_credenciais):
        return None, "Arquivo 'credenciais.json' não encontrado."
    try:
        escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credenciais = ServiceAccountCredentials.from_json_keyfile_name(caminho_credenciais, escopo)
        cliente = gspread.authorize(credenciais)
        planilha = cliente.open("SGP") 
        return planilha, None
    except Exception as e:
        return None, str(e)

planilha, erro_conexao = conectar_google_sheets()

if erro_conexao:
    st.sidebar.error("❌ Conexão Pendente")
    st.sidebar.warning(erro_conexao)
    modo_simulacao = True
else:
    st.sidebar.success("✅ Conectado ao Google Sheets!")
    aba_dados = planilha.worksheet("Cursos_Base_Padronizado")
    modo_simulacao = False

# -----------------------------------------------------------------------------
# CARREGAMENTO DE DADOS COM AUTO-REFRESH (30 SEGUNDOS)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=30)
def carregar_dados():
    if planilha:
        try:
            aba = planilha.worksheet("Cursos_Base_Padronizado")
            dados = aba.get_all_records()
            df = pd.DataFrame(dados)
            df['Previsão de Inicio'] = pd.to_datetime(df['Previsão de Inicio'], errors='coerce')
            df['Previsão de Termino'] = pd.to_datetime(df['Previsão de Termino'], errors='coerce')
            return df, None
        except Exception as e:
            return None, f"Erro ao ler os dados: {str(e)}"
    return None, "Sem conexão ativa."

# -----------------------------------------------------------------------------
# ESTRUTURA DE NAVEGAÇÃO E LISTAS MESTRES
# -----------------------------------------------------------------------------
st.sidebar.title("SGP Operacional")
opcao_tela = st.sidebar.radio(
    "Selecione a Tela:",
    ["🖥️ Painel BI (Sala dos Profs / TV)", "📱 Visão do Professor (Mobile)", "✍️ Administração (Cadastro)"]
)

PROFESSORES_DISPONIVEIS = ['Stepherson', 'Elen', 'Danilo', 'Philipe', 'Bruna', 'Mauricio', 'Daniel', 'Ricardo', 'Everaldo', 'Edson', 'Fábio', 'Renata Aparecida']
SALAS_DISPONIVEIS = ['Sala 01', 'Sala 02', 'Sala 03', 'Sala 04', 'Lab 01', 'Lab 02', 'Ribas - Vila Contenier']
STATUS_OPCOES = ['CONFIRMADO', 'EM ANDAMENTO', 'CONCLUIDO', 'CANCELADO']
TURNOS_OPCOES = ['TARDE', 'NOITE', 'INTEGRAL']

# Pega o horário e data atualizados
agora = datetime.now()
dia_semana_map = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SAB', 6: 'DOM'}
dia_semana_sigla = dia_semana_map[agora.weekday()]

# -----------------------------------------------------------------------------
# TELA 1: PAINEL BI (TV)
# -----------------------------------------------------------------------------
if opcao_tela == "🖥️ Painel BI (Sala dos Profs / TV)":
    
    col_logo, col_relogio = st.columns([3, 1])
    with col_logo:
        st.title("🖥️ Painel de Rastreabilidade Operacional")
        st.write("Coordenação Pedagógica & Monitoramento em Tempo Real")
    with col_relogio:
        st.markdown(f"""
            <div style="text-align: right; padding-top: 10px;">
                <span style="font-size: 16pt; font-weight: bold; color: #60a5fa;">{agora.strftime('%H:%M:%S')}</span><br>
                <span style="font-size: 10pt; color: #94a3b8;">{agora.strftime('%d/%m/%Y')} — <b>{dia_semana_sigla}</b></span>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    df_cursos, erro_dados = carregar_dados()

    if erro_dados or df_cursos is None:
        st.error(f"Erro ao obter dados para o painel: {erro_dados}")
    else:
        data_hoje = pd.to_datetime(agora.date())
        hora_atual_time = agora.time()

        # Filtra as turmas de hoje
        turmas_hoje = df_cursos[
            (df_cursos['Previsão de Inicio'] <= data_hoje) & 
            (df_cursos['Previsão de Termino'] >= data_hoje) & 
            (df_cursos['Dias_Semana_Formatado'].str.contains(dia_semana_sigla, na=False, case=False))
        ]

        professores_em_aula = 0
        salas_ocupadas = set()
        linhas_timeline = []

        for prof in PROFESSORES_DISPONIVEIS:
            cursos_prof = turmas_hoje[turmas_hoje['Professor'] == prof]
            
            curso_atual = None
            curso_anterior = None
            curso_proximo = None

            for idx, row in cursos_prof.iterrows():
                try:
                    h_ini = datetime.strptime(row['Hora_Inicio_Aula'], "%H:%M:%S").time()
                    h_fim = datetime.strptime(row['Hora_Fim_Aula'], "%H:%M:%S").time()
                    
                    if h_ini <= hora_atual_time <= h_fim:
                        curso_atual = row
                        professores_em_aula += 1
                        if pd.notna(row['Local']):
                            salas_ocupadas.add(row['Local'])
                    elif h_fim < hora_atual_time:
                        if curso_anterior is None or h_fim > datetime.strptime(curso_anterior['Hora_Fim_Aula'], "%H:%M:%S").time():
                            curso_anterior = row
                    elif h_ini > hora_atual_time:
                        if curso_proximo is None or h_ini < datetime.strptime(curso_proximo['Hora_Inicio_Aula'], "%H:%M:%S").time():
                            curso_proximo = row
                except:
                    continue

            if curso_atual is not None or curso_anterior is not None or curso_proximo is not None:
                linhas_timeline.append({
                    "Professor": prof,
                    "Anterior": curso_anterior,
                    "Atual": curso_atual,
                    "Proximo": curso_proximo
                })

        # Cards KPIs
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        with col_kpi1:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{professores_em_aula}</div><div class="metric-label">Instrutores em Aula</div></div>', unsafe_allow_html=True)
        with col_kpi2:
            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #60a5fa;">{len(salas_ocupadas)}</div><div class="metric-label">Espaços em Uso</div></div>', unsafe_allow_html=True)
        with col_kpi3:
            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #fbbf24;">{len(turmas_hoje)}</div><div class="metric-label">Total de Turmas Hoje</div></div>', unsafe_allow_html=True)
        with col_kpi4:
            aproveitamento = int((professores_em_aula / len(PROFESSORES_DISPONIVEIS)) * 100) if len(PROFESSORES_DISPONIVEIS) > 0 else 0
            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #f87171;">{aproveitamento}%</div><div class="metric-label">Uso de Alocação</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("⏱️ Status de Ocupação e Rastreamento de Alocação")

        if not linhas_timeline:
            st.info("Nenhum professor ativo ou previsto para hoje!")
        else:
            html_tabela = """
            <table style="width:100%; border-collapse: collapse; background-color: #0b0f19; border: 1px solid #1e293b;">
                <thead>
                    <tr style="background-color: #1e293b;">
                        <th style="padding: 12px; text-align: left; color: #f1f5f9; border-bottom: 2px solid #334155;">Instrutor</th>
                        <th style="padding: 12px; text-align: left; color: #f1f5f9; border-bottom: 2px solid #334155;">Anterior (Concluído Hoje)</th>
                        <th style="padding: 12px; text-align: left; color: #f1f5f9; border-bottom: 2px solid #334155;">Status Atual (Em Sala Agora)</th>
                        <th style="padding: 12px; text-align: left; color: #f1f5f9; border-bottom: 2px solid #334155;">Próximo Previsto</th>
                    </tr>
                </thead>
                <tbody>
            """
            for l in linhas_timeline:
                html_tabela += "<tr style='border-bottom: 1px solid #1e293b;'>"
                html_tabela += f"<td style='padding: 14px; font-weight: bold; color: #ffffff;'>Prof. {l['Professor']}</td>"
                
                # Anterior
                if l['Anterior'] is not None:
                    ant = l['Anterior']
                    html_tabela += f"<td style='padding: 14px;'><span class='status-badge badge-prev'>{ant['CURSO']}</span><br><small style='color: #64748b;'>🕒 {ant['Hora_Inicio_Aula'][:5]}-{ant['Hora_Fim_Aula'][:5]} | 📍 {ant['Local']}</small></td>"
                else:
                    html_tabela += "<td style='padding: 14px; color: #475569; font-style: italic;'>Sem registros</td>"
                
                # Atual
                if l['Atual'] is not None:
                    at = l['Atual']
                    html_tabela += f"<td style='padding: 14px;'><span class='status-badge badge-now'>⚡ {at['CURSO']}</span><br><strong style='color: #34d399;'>🕒 {at['Hora_Inicio_Aula'][:5]}-{at['Hora_Fim_Aula'][:5]} | 📍 {at['Local']}</strong></td>"
                else:
                    html_tabela += "<td style='padding: 14px; color: #475569; font-style: italic;'>Livre / Sem Aula</td>"
                
                # Próximo
                if l['Proximo'] is not None:
                    px = l['Proximo']
                    html_tabela += f"<td style='padding: 14px;'><span class='status-badge badge-next'>⏭️ {px['CURSO']}</span><br><small style='color: #60a5fa;'>🕒 {px['Hora_Inicio_Aula'][:5]}-{px['Hora_Fim_Aula'][:5]} | 📍 {px['Local']}</small></td>"
                else:
                    html_tabela += "<td style='padding: 14px; color: #475569; font-style: italic;'>Sem próximas aulas</td>"
                
                html_tabela += "</tr>"
            html_tabela += "</tbody></table>"
            st.markdown(html_tabela, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# TELA 2: VISÃO DO PROFESSOR (MOBILE RESPONSIVO)
# -----------------------------------------------------------------------------
elif opcao_tela == "📱 Visão do Professor (Mobile)":
    st.title("📱 Portal do Instrutor")
    st.write("Visão simplificada em formato de Linha do Tempo vertical para celulares.")
    st.markdown("---")
    
    # Seletor simples do professor
    prof_selecionado = st.selectbox("Selecione seu Nome:", ["Escolha seu nome..."] + PROFESSORES_DISPONIVEIS)
    
    if prof_selecionado != "Escolha seu nome...":
        df_cursos, erro_dados = carregar_dados()
        
        if erro_dados or df_cursos is None:
            st.error(f"Não foi possível carregar o cronograma: {erro_dados}")
        else:
            data_hoje = pd.to_datetime(agora.date())
            hora_atual_time = agora.time()
            
            # Filtra todas as turmas do professor selecionado para o dia de hoje
            aulas_prof_hoje = df_cursos[
                (df_cursos['Professor'] == prof_selecionado) &
                (df_cursos['Previsão de Inicio'] <= data_hoje) & 
                (df_cursos['Previsão de Termino'] >= data_hoje) & 
                (df_cursos['Dias_Semana_Formatado'].str.contains(dia_semana_sigla, na=False, case=False))
            ]
            
            st.subheader(f"📅 Sua Agenda de Hoje ({agora.strftime('%d/%m/%Y')} — {dia_semana_sigla})")
            
            if aulas_prof_hoje.empty:
                st.info("🎉 Você não tem aulas agendadas para hoje! Aproveite o dia livre.")
            else:
                # Ordena as aulas pelo horário de início
                aulas_prof_hoje = aulas_prof_hoje.sort_values(by="Hora_Inicio_Aula")
                
                # Loop para desenhar os cards empilhados na tela do celular
                for idx, row in aulas_prof_hoje.iterrows():
                    try:
                        h_ini = datetime.strptime(row['Hora_Inicio_Aula'], "%H:%M:%S").time()
                        h_fim = datetime.strptime(row['Hora_Fim_Aula'], "%H:%M:%S").time()
                        
                        # Determina o status da aula em tempo real
                        if h_ini <= hora_atual_time <= h_fim:
                            status_aula = "🟢 EM ANDAMENTO AGORA"
                            card_class = "mobile-card mobile-card-active"
                            horario_cor = "#34d399"
                        elif h_fim < hora_atual_time:
                            status_aula = "⚪ CONCLUÍDA HOJE"
                            card_class = "mobile-card"
                            horario_cor = "#94a3b8"
                        else:
                            status_aula = "🔵 PRÓXIMA PROGRAMADA"
                            card_class = "mobile-card mobile-card-next"
                            horario_cor = "#60a5fa"
                            
                        # Renderiza o Card de Toque Responsivo no Celular
                        st.markdown(f"""
                            <div class="{card_class}">
                                <div style="font-size: 8pt; font-weight: bold; letter-spacing: 0.8px; color: {horario_cor}; margin-bottom: 5px;">
                                    {status_aula}
                                </div>
                                <div style="font-size: 13pt; font-weight: bold; color: #ffffff; margin-bottom: 2px;">
                                    {row['CURSO']}
                                </div>
                                <div style="font-size: 9.5pt; color: #cbd5e1; margin-bottom: 8px;">
                                    📍 <b>Espaço:</b> {row['Local']} — Turno {row['Turno']}
                                </div>
                                <hr style="border: 0; border-top: 1px solid #475569; margin: 8px 0;">
                                <div style="display: flex; justify-content: space-between; font-size: 8.5pt; color: #94a3b8;">
                                    <span>🕒 Horário: <b>{row['Hora_Inicio_Aula'][:5]} às {row['Hora_Fim_Aula'][:5]}</b></span>
                                    <span>📚 Carga Horária: <b>{row['C/H']}h</b></span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                    except Exception as e:
                        continue

# -----------------------------------------------------------------------------
# TELA 3: ADMINISTRAÇÃO (CADASTRO)
# -----------------------------------------------------------------------------
elif opcao_tela == "✍️ Administração (Cadastro)":
    st.title("✍️ Painel Administrativo de Cadastro")
    st.write("Utilize este formulário para alimentar o banco de dados de forma segura no Google Sheets.")
    st.markdown("---")
    
    with st.form("form_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            unidade = st.text_input("Unidade", value="FATEC/ RIBAS")
            status = st.selectbox("Status do Curso", STATUS_OPCOES)
            tipo_curso = st.text_input("Tipo de Curso", value="INICIAÇÃO")
            modalidade = st.selectbox("Modalidade", ["Presencial", "EAD", "Híbrido"])
            codigo_turma = st.text_input("Código da Turma", placeholder="ex: INI.154.PRE.001")
            curso_nome = st.text_input("Nome do Curso / Disciplina*", placeholder="ex: Informática Básica")
            carga_horaria = st.number_input("Carga Horária (C/H)*", min_value=1.0, step=1.0, value=40.0)
            
        with col2:
            data_inicio = st.date_input("Previsão de Início", datetime.today(), format="DD/MM/YYYY")
            data_termino = st.date_input("Previsão de Término", datetime.today(), format="DD/MM/YYYY")
            dias_semana_selecionados = st.multiselect(
                "Dias da Semana*", 
                ["SEG", "TER", "QUA", "QUI", "SEX", "SAB"],
                default=["SEG", "TER", "QUA", "QUI", "SEX"]
            )
            dias_semana_formatado = ",".join(dias_semana_selecionados)
            
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                hora_ini = st.selectbox("Hora de Início*", ["08:00:00", "13:00:00", "13:30:00", "18:00:00", "19:00:00"])
            with col_h2:
                hora_fim = st.selectbox("Hora de Término*", ["12:00:00", "17:00:00", "17:30:00", "22:00:00", "22:30:00"])
                
            local_sala = st.selectbox("Sala / Laboratório*", SALAS_DISPONIVEIS)
            professor_selecionado = st.selectbox("Professor Responsável*", PROFESSORES_DISPONIVEIS)
            turno = st.selectbox("Turno*", TURNOS_OPCOES)
            
        st.markdown("*Campos obrigatórios de validação ativa.*")
        botao_salvar = st.form_submit_button("Salvar na Planilha Google Sheets 🚀")
        
        if botao_salvar:
            if not curso_nome:
                st.error("Erro: O nome do curso é obrigatório!")
            elif modo_simulacao:
                st.error("Erro: Não foi possível gravar. A conexão com o Google Sheets não está ativa.")
            else:
                nova_linha = [
                    unidade, status, tipo_curso, modalidade, codigo_turma, curso_nome, "", 
                    carga_horaria, "", "", str(data_inicio), str(data_termino), 
                    "Seg a Sex" if len(dias_semana_selecionados) == 5 else "Personalizado", 
                    f"{hora_ini[:2]}h as {hora_fim[:2]}h", local_sala, professor_selecionado, turno,
                    professor_selecionado, hora_ini, hora_fim, dias_semana_formatado
                ]
                try:
                    aba_dados = planilha.worksheet("Cursos_Base_Padronizado")
                    aba_dados.append_row(nova_linha)
                    st.success(f"🎉 '{curso_nome}' gravado diretamente no Google Sheets!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")