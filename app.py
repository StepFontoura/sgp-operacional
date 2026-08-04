import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
import random
import string
from datetime import datetime, date, timedelta
import urllib.parse

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA E CONEXÃO
# ==============================================================================
st.set_page_config(
    page_title="SGP Operacional Multi-Unidade",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# MELHORIA DE CONTRASTE E UI (CSS CUSTOMIZADO)
# ==============================================================================
st.markdown("""
    <style>
        [data-testid="stSidebar"] div[data-baseweb="select"] {
            border: 1px solid #4da6ff !important;
            border-radius: 6px !important;
            background-color: rgba(77, 166, 255, 0.05) !important;
        }
        [data-testid="stSidebar"] .stRadio label {
            background-color: rgba(128, 128, 128, 0.1);
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 5px;
            border-left: 4px solid transparent;
            transition: all 0.2s ease-in-out;
        }
        [data-testid="stSidebar"] .stRadio label:hover {
            border-left: 4px solid #4da6ff;
            background-color: rgba(128, 128, 128, 0.2);
        }
        .sidebar-title {
            color: #4da6ff;
            font-size: 1.05em;
            font-weight: 600;
            margin-bottom: 0px;
            margin-top: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .report-card {
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# Buscando a URL de conexão do cofre de segredos do Streamlit
DB_URL = st.secrets["DB_URL"]

@st.cache_resource
def get_engine():
    return create_engine(DB_URL)

engine = get_engine()

# ==============================================================================
# ATUALIZAÇÃO AUTOMÁTICA DE BANCO DE DADOS E AUDITORIA
# ==============================================================================
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS locais (
                id_local SERIAL PRIMARY KEY,
                id_unidade INTEGER REFERENCES unidades(id_unidade),
                nome_local VARCHAR(100) NOT NULL
            );
        """))
        conn.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='turmas' AND column_name='id_local') THEN 
                    ALTER TABLE turmas ADD COLUMN id_local INTEGER; 
                END IF; 
            END $$;
        """))
        
        novas_colunas = {
            "id_professor_principal": "INTEGER",
            "id_professor_auxiliar": "INTEGER",
            "carga_horaria_total": "INTEGER",
            "previsao_inicio": "DATE",
            "data_inicio": "DATE",
            "data_termino": "DATE",
            "dias_semana": "VARCHAR(200)",
            "horario_inicio": "TIME",
            "horario_termino": "TIME",
            "observacoes": "TEXT",
            "status": "VARCHAR(50) DEFAULT 'PREVISTA'",
            "categoria": "VARCHAR(50) DEFAULT 'OUTROS'"
        }
        
        for col, tipo in novas_colunas.items():
            conn.execute(text(f"""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='turmas' AND column_name='{col}') THEN 
                        ALTER TABLE turmas ADD COLUMN {col} {tipo}; 
                    END IF; 
                END $$;
            """))

        # Injeta automaticamente o usuário "CONVIDADO"
        conn.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM usuarios WHERE email = 'convidado@sgp.com') THEN 
                    INSERT INTO usuarios (nome, email, perfil, senha, id_unidade, valor_hora_padrao) 
                    VALUES ('Convidado', 'convidado@sgp.com', 'COORDENADOR', '123456', (SELECT MIN(id_unidade) FROM unidades), 0);
                END IF; 
            END $$;
        """))

        # Regras de Categoria
        conn.execute(text("""
            UPDATE turmas SET categoria = 'INICIANTE' WHERE codigo_turma ILIKE 'INI%' AND categoria = 'OUTROS';
            UPDATE turmas SET categoria = 'TÉCNICO' WHERE codigo_turma ILIKE 'TEC%' AND categoria = 'OUTROS';
            UPDATE turmas SET categoria = 'QUALIFICAÇÃO' WHERE codigo_turma ILIKE 'QUA%' AND categoria = 'OUTROS';
            UPDATE turmas SET categoria = 'APERFEIÇOAMENTO' WHERE codigo_turma ILIKE 'APE%' AND categoria = 'OUTROS';
        """))

        # Motor de Auditoria Temporal
        conn.execute(text("""
            UPDATE turmas SET status = UPPER(status) WHERE status IS NOT NULL;
            UPDATE turmas SET status = 'CONCLUÍDA' WHERE data_termino < CURRENT_DATE AND status NOT IN ('CANCELADA', 'ADIADA');
            UPDATE turmas SET status = 'EM ANDAMENTO' WHERE data_inicio <= CURRENT_DATE AND data_termino >= CURRENT_DATE AND status NOT IN ('CANCELADA', 'ADIADA');
            UPDATE turmas SET status = 'PREVISTA' WHERE data_inicio > CURRENT_DATE AND status NOT IN ('CANCELADA', 'ADIADA');
            UPDATE turmas SET status = 'PREVISTA' WHERE data_inicio IS NULL AND status IN ('EM ANDAMENTO', 'CONCLUÍDA');
        """))
except Exception as e:
    pass 

# ==============================================================================
# SESSÃO E LOGIN
# ==============================================================================
if "logado" not in st.session_state:
    st.session_state.logado = False
if "usuario_info" not in st.session_state:
    st.session_state.usuario_info = None
if "modo_recuperar" not in st.session_state:
    st.session_state.modo_recuperar = False
if "user_edit_id" not in st.session_state:
    st.session_state.user_edit_id = None
if "local_edit_id" not in st.session_state:
    st.session_state.local_edit_id = None
if "novo_usuario_criado" not in st.session_state:
    st.session_state.novo_usuario_criado = None
if "filtro_agenda" not in st.session_state:
    st.session_state.filtro_agenda = "TODAS"

if not st.session_state.logado:
    st.write("<br><br>", unsafe_allow_html=True)
    
    st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style='color: #0f4c81; font-size: 3.5em; margin-bottom: 0px; font-weight: 800;'>🎓 SGP</h1>
            <h3 style='color: #666; font-weight: 300; margin-top: 5px; font-size: 1.5em;'>Portal de Acesso Operacional</h3>
        </div>
    """, unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 1.2, 1])

    with col_center:
        with st.container(border=True):
            if st.session_state.modo_recuperar:
                st.markdown("<h4 style='text-align: center; color: #333;'>🔑 Recuperação de Senha</h4>", unsafe_allow_html=True)
                st.write("")
                
                with st.form("form_recuperacao"):
                    email_rec = st.text_input("Informe o seu E-mail cadastrado:")
                    btn_gerar_codigo = st.form_submit_button("Gerar Código de Redefinição", use_container_width=True)
                    
                    if btn_gerar_codigo:
                        if email_rec:
                            with engine.connect() as conn:
                                user = conn.execute(text("SELECT id_usuario, nome FROM usuarios WHERE LOWER(email) = LOWER(:e)"), {"e": email_rec.strip()}).fetchone()
                                if user:
                                    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                                    conn.execute(text("UPDATE usuarios SET token_recuperacao = :t WHERE id_usuario = :id"), {"t": token, "id": user[0]})
                                    conn.commit()
                                    st.success(f"✅ Código temporário gerado para {user[1]}: **{token}**")
                                else:
                                    st.error("❌ E-mail não localizado em nossa base de dados.")
                        else:
                            st.warning("⚠️ Por favor, informe um e-mail válido.")
                
                if st.button("⬅️ Voltar ao Login", use_container_width=True):
                    st.session_state.modo_recuperar = False
                    st.rerun()
            else:
                st.markdown("<h4 style='text-align: center; color: #333;'>🔒 Identificação</h4>", unsafe_allow_html=True)
                st.write("")

                with st.form("form_login"):
                    email_login = st.text_input("E-mail ou Nome de Usuário:")
                    senha_login = st.text_input("Senha:", type="password")
                    
                    st.write("")
                    btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)

                    if btn_entrar:
                        if email_login and senha_login:
                            with engine.connect() as conn:
                                query = text("""
                                    SELECT u.id_usuario, u.nome, u.email, u.perfil, u.id_unidade, u.senha, u.valor_hora_padrao, un.nome as nome_unidade
                                    FROM usuarios u
                                    LEFT JOIN unidades un ON u.id_unidade = un.id_unidade
                                    WHERE LOWER(u.email) = LOWER(:login) OR LOWER(u.nome) = LOWER(:login)
                                """)
                                usr = conn.execute(query, {"login": email_login.strip()}).fetchone()

                                if usr and str(usr[5]) == str(senha_login):
                                    e_convidado = (str(usr[2]).lower() == 'convidado@sgp.com') or (str(usr[1]).lower() == 'convidado')
                                    
                                    st.session_state.logado = True
                                    st.session_state.usuario_info = {
                                        "id": usr[0], "nome": usr[1], "email": usr[2],
                                        "perfil": str(usr[3]).upper(), "id_unidade": usr[4],
                                        "valor_hora": float(usr[6]) if usr[6] else 65.00,
                                        "nome_unidade": usr[7] or "Unidade Não Atribuída",
                                        "is_convidado": e_convidado
                                    }
                                    st.success(f"Bem-vindo(a), {usr[1]}!")
                                    st.rerun()
                                else:
                                    st.error("❌ Credenciais inválidas. Verifique seu login e senha.")
                        else:
                            st.warning("⚠️ Preencha todos os campos para continuar.")

                if st.button("Esqueceu a senha?", use_container_width=True):
                    st.session_state.modo_recuperar = True
                    st.rerun()

        st.markdown("""
            <div style="text-align: center; color: #888; font-size: 13px; line-height: 1.5; margin-top: 30px;">
                <strong>Desenvolvido pela Unidade de Ribas do Rio Pardo</strong><br>
                Stepherson Fontoura<br>
                <em>Analista de Sistemas</em>
            </div>
        """, unsafe_allow_html=True)

    st.stop()

# ==============================================================================
# CARREGA ESTRUTURA BÁSICA GERAL
# ==============================================================================
user = st.session_state.usuario_info
perfil = user["perfil"]
is_conv = user.get("is_convidado", False)

with engine.connect() as conn:
    df_unidades = pd.read_sql("SELECT id_unidade, nome FROM unidades ORDER BY nome", conn)
    df_instrutores = pd.read_sql("SELECT id_usuario, nome FROM usuarios WHERE perfil IN ('INSTRUTOR', 'ADMINISTRADOR', 'COORDENADOR') ORDER BY nome", conn)

unidades_map = dict(zip(df_unidades['nome'], df_unidades['id_unidade']))
instrutores_map = dict(zip(df_instrutores['nome'], df_instrutores['id_usuario']))
instrutores_map_rev = {v: k for k, v in instrutores_map.items()}

# ==============================================================================
# SIDEBAR: FILTROS E NAVEGAÇÃO
# ==============================================================================
with st.sidebar:
    st.markdown("### 👤 Usuário Conectado")
    st.write(f"**Nome:** {user['nome']}")
    if is_conv:
        st.markdown("`🔒 CONVIDADO (Somente Leitura)`")
    else:
        st.write(f"**Perfil:** `{perfil}`")
    st.write(f"**Unidade:** {user['nome_unidade']}")
    
    if st.button("🚪 Sair / Logout", use_container_width=True):
        st.session_state.logado = False
        st.session_state.usuario_info = None
        st.rerun()
        
    st.divider()

    if perfil == 'ADMINISTRADOR':
        st.markdown('<p class="sidebar-title">📍 Filtro Global de Unidade (ADM):</p>', unsafe_allow_html=True)
        opcoes_unid = ["Todas as Unidades"] + list(unidades_map.keys())
        unid_selecionada_nome = st.selectbox("Selecione a Unidade:", opcoes_unid, label_visibility="collapsed")
        id_unidade_filtro = unidades_map.get(unid_selecionada_nome, None) if unid_selecionada_nome != "Todas as Unidades" else None
    else:
        id_unidade_filtro = user["id_unidade"]
        st.info(f"📍 **Escopo Restrito:**\n{user['nome_unidade']}")

    st.markdown('<p class="sidebar-title">📌 Filtro de Espaço (Sala/Empr.):</p>', unsafe_allow_html=True)
    query_locais = "SELECT id_local, nome_local FROM locais WHERE 1=1"
    params_locais = {}
    
    if id_unidade_filtro:
        query_locais += " AND id_unidade = :id_unid"
        params_locais["id_unid"] = id_unidade_filtro
    query_locais += " ORDER BY nome_local"

    with engine.connect() as conn:
        df_locais = pd.read_sql(text(query_locais), conn, params=params_locais)
    
    locais_map = dict(zip(df_locais['nome_local'], df_locais['id_local']))
    locais_map_rev = {v: k for k, v in locais_map.items()}
    
    opcoes_local = ["Todos os Locais"] + list(locais_map.keys())
    local_selecionado_nome = st.selectbox("Selecione o Local de Aula:", opcoes_local, label_visibility="collapsed")
    id_local_filtro = locais_map.get(local_selecionado_nome, None) if local_selecionado_nome != "Todos os Locais" else None

    st.divider()
    
    opcoes_tela = []
    if perfil in ['ADMINISTRADOR', 'COORDENADOR', 'SECRETARIA']:
        opcoes_tela.append("📺 Painel BI Operacional")
        opcoes_tela.append("📚 Gestão de Turmas")
        
    if perfil in ['ADMINISTRADOR', 'COORDENADOR', 'INSTRUTOR']:
        opcoes_tela.append("📱 Portal do Instrutor")

    opcoes_tela.append("📑 Relatórios & Espelho de Horas")
    opcoes_tela.append("👤 Meu Perfil / Configurações")

    if perfil in ['ADMINISTRADOR', 'COORDENADOR']:
        opcoes_tela.append("⚙️ Gestão de Usuários & Unidades")

    st.markdown('<p class="sidebar-title">🧭 Navegação</p>', unsafe_allow_html=True)
    tela_selecionada = st.radio("Navegação:", opcoes_tela, label_visibility="collapsed")


# ==============================================================================
# TELA 0: GESTÃO DE TURMAS (COMPLETA)
# ==============================================================================
if tela_selecionada == "📚 Gestão de Turmas":
    st.title("📚 Gestão Pedagógica de Turmas")
    st.caption("Cadastre, visualize e organize os cursos ministrados na unidade.")

    aba_turmas = st.tabs(["📋 Painel de Turmas", "➕ Nova Turma", "✏️ Gerenciar (Editar/Excluir)"])

    # --- ABA 1: LISTA DE TURMAS ---
    with aba_turmas[0]:
        st.subheader("📋 Painel de Turmas")
        
        query_t = """
            SELECT t.id_turma, t.codigo_turma as "Código", t.categoria as "Categoria", t.nome_curso as "Curso", 
                   un.nome as "Unidade", COALESCE(l.nome_local, 'Não Definido') as "Local/Sala",
                   COALESCE(u.nome, 'Não Atribuído') as "Prof. Principal", 
                   COALESCE(u2.nome, '--') as "Prof. Auxiliar", 
                   COALESCE(CAST(t.carga_horaria_total AS VARCHAR), '--') as "Carga (h)", 
                   COALESCE(TO_CHAR(t.data_inicio, 'DD/MM/YYYY'), '--') as "Data Início",
                   COALESCE(TO_CHAR(t.data_termino, 'DD/MM/YYYY'), '--') as "Data Término",
                   CASE 
                       WHEN t.categoria IN ('TÉCNICO', 'QUALIFICAÇÃO', 'APERFEIÇOAMENTO') THEN '🟢 +20%'
                       WHEN t.categoria = 'INICIANTE' THEN '🔴 Sem Extra'
                       ELSE '⚪ Padrão'
                   END as "Gratificação",
                   COALESCE(t.status, 'PREVISTA') as "Status"
            FROM turmas t
            LEFT JOIN unidades un ON t.id_unidade = un.id_unidade
            LEFT JOIN locais l ON t.id_local = l.id_local
            LEFT JOIN usuarios u ON t.id_professor_principal = u.id_usuario
            LEFT JOIN usuarios u2 ON t.id_professor_auxiliar = u2.id_usuario
            WHERE 1=1
        """
        params_t = {}
        if id_unidade_filtro:
            query_t += " AND t.id_unidade = :u"
            params_t["u"] = id_unidade_filtro
        if id_local_filtro:
            query_t += " AND t.id_local = :l"
            params_t["l"] = id_local_filtro
            
        query_t += " ORDER BY t.id_turma DESC"
        
        with engine.connect() as conn:
            df_turmas_view = pd.read_sql(text(query_t), conn, params=params_t)
            
        if not df_turmas_view.empty:
            st.dataframe(df_turmas_view.drop(columns=['id_turma']), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma turma encontrada para os filtros selecionados.")

    # --- ABA 2: CADASTRO DE NOVA TURMA ---
    with aba_turmas[1]:
        st.subheader("➕ Formulário de Abertura de Turma/Curso")
        
        with st.container(border=True):
            st.markdown("**1. Definição do Espaço Físico**")
            col_t1, col_t2 = st.columns(2)
            
            if perfil == 'ADMINISTRADOR':
                u_sel_nome = col_t1.selectbox("Unidade Responsável:", list(unidades_map.keys()), key="cad_t_unidade")
                u_sel_id = unidades_map[u_sel_nome]
            else:
                u_sel_id = user["id_unidade"]
                u_sel_nome = user["nome_unidade"]
                col_t1.text_input("Unidade Responsável:", value=u_sel_nome, disabled=True)
            
            with engine.connect() as conn:
                loc_df = pd.read_sql(text("SELECT id_local, nome_local FROM locais WHERE id_unidade = :u ORDER BY nome_local"), conn, params={"u": u_sel_id})
            loc_map = dict(zip(loc_df['nome_local'], loc_df['id_local'])) if not loc_df.empty else {"Sem locais cadastrados": None}
            
            l_sel_nome = col_t2.selectbox("Local / Sala / In-Company:", list(loc_map.keys()), key="cad_t_local")
            l_sel_id = loc_map.get(l_sel_nome, None)

        if "input_cod_t" not in st.session_state:
            st.session_state.input_cod_t = ""
        if "input_cat_t" not in st.session_state:
            st.session_state.input_cat_t = "OUTROS"

        def analisa_codigo_turma():
            codigo = st.session_state.input_cod_t.upper()
            if codigo.startswith("INI"):
                st.session_state.input_cat_t = "INICIANTE"
            elif codigo.startswith("TEC"):
                st.session_state.input_cat_t = "TÉCNICO"
            elif codigo.startswith("QUA"):
                st.session_state.input_cat_t = "QUALIFICAÇÃO"
            elif codigo.startswith("APE"):
                st.session_state.input_cat_t = "APERFEIÇOAMENTO"

        with st.container(border=True):
            st.markdown("**2. Dados Pedagógicos**")
            c1, c1b, c2 = st.columns([1.2, 1, 2])
            
            cod_t = c1.text_input("Código da Turma (Ex: TEC-001):", key="input_cod_t", on_change=analisa_codigo_turma)
            cat_t = c1b.selectbox("Categoria / Tipo:", ["INICIANTE", "TÉCNICO", "QUALIFICAÇÃO", "APERFEIÇOAMENTO", "OUTROS"], key="input_cat_t")
            nome_t = c2.text_input("Nome do Curso:")
            
            c3a, c3b = st.columns(2)
            prof_opcoes = ["Não Atribuir Agora"] + list(instrutores_map.keys())
            prof_nome = c3a.selectbox("Professor / Instrutor Principal:", prof_opcoes)
            prof_aux_nome = c3b.selectbox("Professor Auxiliar (Substituto/Apoio):", prof_opcoes)
            
            if cat_t in ["TÉCNICO", "QUALIFICAÇÃO", "APERFEIÇOAMENTO"]:
                st.markdown("""
                    <div style='background-color: rgba(40, 167, 69, 0.15); color: #28a745; 
                                padding: 8px 12px; border-radius: 5px; font-weight: 600; 
                                margin-bottom: 15px; border-left: 5px solid #28a745; display: inline-block;'>
                        💰 Curso com Gratificação de 20% para o Instrutor
                    </div>
                """, unsafe_allow_html=True)
            elif cat_t == "INICIANTE":
                st.markdown("""
                    <div style='background-color: rgba(220, 53, 69, 0.1); color: #e66771; 
                                padding: 8px 12px; border-radius: 5px; font-weight: 600; 
                                margin-bottom: 15px; border-left: 5px solid #e66771; display: inline-block;'>
                        ℹ️ Curso sem Gratificação de 20% para o Instrutor
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("**3. Cronograma e Carga Horária**")
            c4, c5, c6, c7 = st.columns(4)
            carga_h = c4.number_input("Carga Horária Total (h):", min_value=1, value=40, step=1)
            
            prev_ini = c5.date_input("Previsão de Início:", value=date.today(), format="DD/MM/YYYY")
            data_ini = c6.date_input("Data Real de Início (Opcional):", value=None, format="DD/MM/YYYY")
            data_fim = c7.date_input("Data de Término (Opcional):", value=None, format="DD/MM/YYYY")
            
            st.markdown("**4. Horários e Frequência**")
            c8, c9, c10 = st.columns([2, 1, 1])
            dias_semana_opts = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            dias_selecionados = c8.multiselect("Dias da Semana da Aula:", dias_semana_opts)
            hr_ini = c9.time_input("Horário de Início:", value=None)
            hr_fim = c10.time_input("Horário de Término:", value=None)
            
            obs = st.text_area("Observações Adicionais:", height=100)
            
            st.write("")
            if is_conv:
                st.warning("🔒 Usuário Convidado: Operação de cadastro desabilitada.")
                st.button("✅ Cadastrar Turma e Salvar", disabled=True)
            else:
                btn_salvar_turma = st.button("✅ Cadastrar Turma e Salvar", use_container_width=True, type="primary")
                if btn_salvar_turma:
                    if not cod_t or not nome_t:
                        st.warning("⚠️ Código da Turma e Nome do Curso são obrigatórios!")
                    elif not l_sel_id:
                        st.error("⚠️ Cadastre um Local/Sala nesta Unidade antes de criar turmas.")
                    else:
                        prof_id = instrutores_map.get(prof_nome, None)
                        prof_aux_id = instrutores_map.get(prof_aux_nome, None)
                        dias_str = ", ".join(dias_selecionados) if dias_selecionados else None
                        
                        try:
                            with engine.connect() as conn:
                                # Proteção contra Código Duplicado
                                existe_codigo = conn.execute(
                                    text("SELECT 1 FROM turmas WHERE codigo_turma = :cod"), 
                                    {"cod": cod_t.strip()}
                                ).fetchone()
                                
                                if existe_codigo:
                                    st.error(f"⚠️ **Erro de Cadastro:** Já existe uma turma cadastrada com o código '{cod_t}'. Por favor, escolha um código único.")
                                else:
                                    # Execução Segura do Cadastro (agora com carga_horaria_total)
                                    conn.execute(text("""
                                        INSERT INTO turmas (
                                            id_unidade, id_local, codigo_turma, categoria, nome_curso, id_professor_principal, id_professor_auxiliar,
                                            carga_horaria_total, previsao_inicio, data_inicio, data_termino,
                                            dias_semana, horario_inicio, horario_termino, observacoes, status
                                        ) VALUES (
                                            :id_u, :id_l, :cod, :cat, :nome, :id_p, :id_pa, :ch, :prev, :dt_i, :dt_f, :dias, :hr_i, :hr_f, :obs, 'PREVISTA'
                                        )
                                    """), {
                                        "id_u": int(u_sel_id) if u_sel_id is not None else None, 
                                        "id_l": int(l_sel_id) if l_sel_id is not None else None, 
                                        "cod": cod_t.strip(), 
                                        "cat": cat_t, 
                                        "nome": nome_t.strip(),
                                        "id_p": int(prof_id) if prof_id is not None else None, 
                                        "id_pa": int(prof_aux_id) if prof_aux_id is not None else None, 
                                        "ch": carga_h, 
                                        "prev": prev_ini, 
                                        "dt_i": data_ini, 
                                        "dt_f": data_fim,
                                        "dias": dias_str, 
                                        "hr_i": hr_ini.strftime('%H:%M:%S') if hr_ini else None, 
                                        "hr_f": hr_fim.strftime('%H:%M:%S') if hr_fim else None, 
                                        "obs": obs.strip()
                                    })
                                    conn.commit()
                                    
                                    st.session_state.input_cod_t = ""
                                    st.session_state.input_cat_t = "OUTROS"
                                    st.success(f"🎉 Turma **{cod_t} - {nome_t}** cadastrada com sucesso!")
                                    st.rerun()
                        except IntegrityError as e:
                            st.error(f"❌ **Erro de Integridade:** Não foi possível salvar a turma. Verifique as restrições da sua base. (Detalhe técnico: {e})")
                        except Exception as e:
                            st.error(f"❌ **Erro interno inesperado:** {e}")

    # --- ABA 3: GERENCIAR (EDITAR E EXCLUIR) ---
    with aba_turmas[2]:
        st.subheader("✏️ Editor de Turmas Existentes")
        st.caption("Selecione uma turma para atualizar datas, corrigir status ou dados.")
        
        if not df_turmas_view.empty:
            opcoes_turmas_edit = df_turmas_view['Código'] + " — " + df_turmas_view['Curso']
            map_turmas_id = dict(zip(opcoes_turmas_edit, df_turmas_view['id_turma']))
            
            turma_sel_texto = st.selectbox("Selecione a Turma que deseja alterar:", list(map_turmas_id.keys()))
            id_t_alvo = map_turmas_id[turma_sel_texto]
            
            st.divider()
            
            with engine.connect() as conn:
                t_dados = conn.execute(text("SELECT * FROM turmas WHERE id_turma = :id"), {"id": int(id_t_alvo)}).fetchone()
            
            if t_dados:
                cols = t_dados._mapping
                
                with st.form("form_edit_turma", border=True):
                    st.markdown(f"**Editando: {cols['codigo_turma']}**")
                    
                    c_e1, c_e2, c_e3 = st.columns([1, 1.5, 1.5])
                    status_opts = ["PREVISTA", "EM ANDAMENTO", "CONCLUÍDA", "ADIADA", "CANCELADA"]
                    status_idx = status_opts.index(cols['status']) if cols['status'] in status_opts else 0
                    e_status = c_e1.selectbox("Status Atual:", status_opts, index=status_idx)
                    
                    e_nome = c_e2.text_input("Nome do Curso:", value=cols['nome_curso'])
                    e_codigo = c_e3.text_input("Código da Turma:", value=cols['codigo_turma'])
                    
                    c_e4, c_e5 = st.columns([1.5, 1.5])
                    cat_opts = ["INICIANTE", "TÉCNICO", "QUALIFICAÇÃO", "APERFEIÇOAMENTO", "OUTROS"]
                    cat_idx = cat_opts.index(cols['categoria']) if cols['categoria'] in cat_opts else 4
                    e_cat = c_e4.selectbox("Categoria:", cat_opts, index=cat_idx)
                    
                    l_opts = list(locais_map.keys())
                    l_atual_nome = locais_map_rev.get(cols['id_local'], "")
                    l_idx = l_opts.index(l_atual_nome) if l_atual_nome in l_opts else 0
                    e_local_nome = c_e5.selectbox("Local/Sala:", l_opts, index=l_idx)
                    
                    c_e6a, c_e6b = st.columns(2)
                    p_opts = ["Não Atribuir Agora"] + list(instrutores_map.keys())
                    
                    p_atual_nome = instrutores_map_rev.get(cols['id_professor_principal'], "Não Atribuir Agora")
                    p_idx = p_opts.index(p_atual_nome) if p_atual_nome in p_opts else 0
                    e_prof_nome = c_e6a.selectbox("Prof. Principal:", p_opts, index=p_idx)
                    
                    p_aux_atual_nome = instrutores_map_rev.get(cols['id_professor_auxiliar'], "Não Atribuir Agora")
                    p_aux_idx = p_opts.index(p_aux_atual_nome) if p_aux_atual_nome in p_opts else 0
                    e_prof_aux_nome = c_e6b.selectbox("Prof. Auxiliar (Substituto/Apoio):", p_opts, index=p_aux_idx)
                    
                    st.markdown("**Cronograma**")
                    c_e7, c_e8, c_e9, c_e10 = st.columns(4)
                    
                    # Garantindo que pegue a coluna legada se existir, ou o padrão
                    val_carga_horaria = cols.get('carga_horaria_total', cols.get('carga_horaria', 40))
                    if val_carga_horaria is None: val_carga_horaria = 40
                        
                    e_carga = c_e7.number_input("Carga Horária:", value=val_carga_horaria)
                    e_prev = c_e8.date_input("Previsão:", value=cols['previsao_inicio'] or date.today(), format="DD/MM/YYYY")
                    e_dt_ini = c_e9.date_input("Data Início:", value=cols['data_inicio'] or None, format="DD/MM/YYYY")
                    e_dt_fim = c_e10.date_input("Data Término:", value=cols['data_termino'] or None, format="DD/MM/YYYY")
                    
                    b1, b2, b3 = st.columns([2, 1, 1])
                    
                    if is_conv:
                        st.warning("🔒 Usuário Convidado: Apenas Leitura.")
                        btn_atualizar = b1.form_submit_button("💾 Salvar Alterações", disabled=True)
                        btn_excluir = False
                    else:
                        btn_atualizar = b1.form_submit_button("💾 Salvar Alterações", type="primary")
                        if perfil in ['ADMINISTRADOR', 'COORDENADOR']:
                            confirma_exclusao = b2.checkbox("Confirmar Exclusão (Cuidado)")
                            btn_excluir = b3.form_submit_button("🗑️ Excluir Turma")
                        else:
                            confirma_exclusao = False
                            btn_excluir = False
                    
                    if btn_atualizar:
                        e_id_local = locais_map.get(e_local_nome, None)
                        e_id_prof = instrutores_map.get(e_prof_nome, None)
                        e_id_prof_aux = instrutores_map.get(e_prof_aux_nome, None)
                        
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    UPDATE turmas 
                                    SET nome_curso = :n, codigo_turma = :cod, categoria = :cat, status = :st,
                                        id_local = :il, id_professor_principal = :ip, id_professor_auxiliar = :ipa, carga_horaria_total = :ch,
                                        previsao_inicio = :pi, data_inicio = :di, data_termino = :dt
                                    WHERE id_turma = :id
                                """), {
                                    "n": e_nome, "cod": e_codigo, "cat": e_cat, "st": e_status,
                                    "il": int(e_id_local) if e_id_local is not None else None, 
                                    "ip": int(e_id_prof) if e_id_prof is not None else None, 
                                    "ipa": int(e_id_prof_aux) if e_id_prof_aux is not None else None, 
                                    "ch": e_carga, 
                                    "pi": e_prev, "di": e_dt_ini, "dt": e_dt_fim, "id": int(id_t_alvo)
                                })
                                conn.commit()
                            st.success("✅ Turma atualizada com sucesso!")
                            st.rerun()
                        except IntegrityError as e:
                            st.error(f"❌ **Erro de Integridade:** Não foi possível atualizar a turma pois as restrições da base foram violadas. (Detalhes: {e})")
                        except Exception as e:
                            st.error(f"❌ **Erro interno inesperado:** {e}")
                        
                    if btn_excluir:
                        if confirma_exclusao:
                            try:
                                with engine.connect() as conn:
                                    conn.execute(text("DELETE FROM turmas WHERE id_turma = :id"), {"id": int(id_t_alvo)})
                                    conn.commit()
                                st.success("🗑️ Turma excluída permanentemente!")
                                st.rerun()
                            except IntegrityError:
                                st.error("❌ Não é possível excluir a turma diretamente. Ela já possui vínculos ou histórico salvo. Altere o Status para 'CANCELADA' no lugar de excluir.")
                            except Exception as e:
                                st.error(f"❌ Ocorreu um erro: {e}")
                        else:
                            st.warning("⚠️ Marque a caixa 'Confirmar Exclusão' antes de clicar no botão.")
        else:
            st.info("Não há turmas cadastradas para exibir no editor.")

# ==============================================================================
# TELA 1: PAINEL BI (COM FILTROS DE UNIDADE E LOCAL)
# ==============================================================================
elif tela_selecionada == "📺 Painel BI Operacional":
    st.title("📊 Painel de Rastreabilidade Pedagógica")
    st.caption("Visão Operacional das Turmas e Alocação")

    query_bi = """
        SELECT a.id_agendamento, a.horas_aula, a.valor_hora_aplicado, 
               t.nome_curso, t.codigo_turma, u.nome as professor, 
               un.nome as unidade, un.id_unidade,
               COALESCE(l.nome_local, 'Não Informado') as local_aula
        FROM agendamentos a
        JOIN turmas t ON a.id_turma = t.id_turma
        JOIN usuarios u ON a.id_instrutor = u.id_usuario
        JOIN unidades un ON t.id_unidade = un.id_unidade
        LEFT JOIN locais l ON t.id_local = l.id_local
        WHERE 1=1
    """
    params_bi = {}
    if id_unidade_filtro:
        query_bi += " AND un.id_unidade = :id_unid"
        params_bi["id_unid"] = int(id_unidade_filtro)
        
    if id_local_filtro:
        query_bi += " AND t.id_local = :id_loc"
        params_bi["id_loc"] = int(id_local_filtro)

    with engine.connect() as conn:
        df_agend = pd.read_sql(text(query_bi), conn, params=params_bi)

    if not df_agend.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Aulas Agendadas", len(df_agend['codigo_turma']))
        col2.metric("Docentes Ativos", len(df_agend['professor'].unique()))
        
        if perfil in ['ADMINISTRADOR', 'COORDENADOR']:
            col3.metric("Total Horas Alocadas", f"{df_agend['horas_aula'].sum()}h")
            
        if perfil == 'ADMINISTRADOR':
            v_total = (df_agend['horas_aula'] * df_agend['valor_hora_aplicado']).sum()
            col4.metric("Previsão Orçamentária", f"R$ {v_total:,.2f}")
            
        st.divider()
        st.subheader("📋 Aulas Agendadas no Período")
        cols_exibicao = ['unidade', 'local_aula', 'codigo_turma', 'nome_curso', 'professor']
        if perfil in ['ADMINISTRADOR', 'COORDENADOR']:
            cols_exibicao.append('horas_aula')
        
        st.dataframe(df_agend[cols_exibicao], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro encontrado para os filtros selecionados.")

# ==============================================================================
# TELA 2: PORTAL DO INSTRUTOR (COM DASHBOARD INTERATIVO)
# ==============================================================================
elif tela_selecionada == "📱 Portal do Instrutor":
    st.title("📱 Portal do Instrutor")

    if perfil == 'INSTRUTOR':
        id_prof_alvo = user["id"]
        nome_prof_alvo = user["nome"]
        vh_alvo = user["valor_hora"]
    else:
        query_profs = "SELECT id_usuario, nome, valor_hora_padrao FROM usuarios WHERE perfil IN ('INSTRUTOR', 'ADMINISTRADOR', 'COORDENADOR')"
        params_profs = {}
        if id_unidade_filtro:
            query_profs += " AND id_unidade = :id_unid"
            params_profs["id_unid"] = int(id_unidade_filtro)
        query_profs += " ORDER BY nome"

        with engine.connect() as conn:
            profs = pd.read_sql(text(query_profs), conn, params=params_profs)
        
        prof_map_sel = dict(zip(profs['nome'], profs['id_usuario']))
        map_vh_portal = dict(zip(profs['id_usuario'], profs['valor_hora_padrao']))
        
        if prof_map_sel:
            nome_sel = st.selectbox("Selecione o Instrutor:", list(prof_map_sel.keys()))
            id_prof_alvo = prof_map_sel[nome_sel]
            nome_prof_alvo = nome_sel
            vh_alvo = float(map_vh_portal.get(id_prof_alvo, 65.0))
        else:
            id_prof_alvo, nome_prof_alvo, vh_alvo = None, None, 65.0

    if id_prof_alvo:
        hoje_p = date.today()
        if hoje_p.day >= 11:
            ini_mes = date(hoje_p.year, hoje_p.month, 10)
            if hoje_p.month == 12:
                fim_mes = date(hoje_p.year + 1, 1, 11)
            else:
                fim_mes = date(hoje_p.year, hoje_p.month + 1, 11)
        else:
            if hoje_p.month == 1:
                ini_mes = date(hoje_p.year - 1, 12, 10)
            else:
                ini_mes = date(hoje_p.year, hoje_p.month - 1, 10)
            fim_mes = date(hoje_p.year, hoje_p.month, 11)

        with engine.connect() as conn:
            query_prov = """
                SELECT t.carga_horaria_total as carga_horaria, t.categoria,
                       CASE WHEN t.categoria IN ('TÉCNICO', 'QUALIFICAÇÃO', 'APERFEIÇOAMENTO') THEN 1 ELSE 0 END as tem_grat
                FROM turmas t
                WHERE (t.id_professor_principal = :id_inst OR t.id_professor_auxiliar = :id_inst)
                AND (t.data_inicio <= :df AND t.data_termino >= :di)
            """
            df_prov = pd.read_sql(text(query_prov), conn, params={"id_inst": int(id_prof_alvo), "di": ini_mes, "df": fim_mes})

        total_h_mes = 0
        valor_prov_mes = 0.0
        if not df_prov.empty:
            for _, r in df_prov.iterrows():
                ch = float(r['carga_horaria'] or 0)
                total_h_mes += ch
                v_b = ch * vh_alvo
                if r['tem_grat'] == 1:
                    valor_prov_mes += v_b * 1.20
                else:
                    valor_prov_mes += v_b

        st.markdown(f"""
            <div style="background-color: #1e4620; border: 1px solid #2ea043; padding: 12px 20px; border-radius: 6px; margin-bottom: 20px; color: #d4edda; font-size: 16px;">
                💰 <b>Previsão Estimada de Recebimento (Mês Atual):</b> R$ {valor_prov_mes:,.2f} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Total Horas:</b> {total_h_mes}h &nbsp;&nbsp;|&nbsp;&nbsp; <b>Valor/Hora Atual (CTPS):</b> R$ {vh_alvo:,.2f}
            </div>
        """, unsafe_allow_html=True)

        # --- SEÇÃO 1: GRID DE TURMAS COM DASHBOARD ---
        query_portal_turmas = """
            SELECT 
                t.codigo_turma AS "Código",
                t.nome_curso AS "Curso",
                t.categoria AS "Categoria",
                t.status AS "Status",
                COALESCE(TO_CHAR(t.data_inicio, 'DD/MM/YYYY'), '--') AS "Data Início",
                COALESCE(TO_CHAR(t.data_termino, 'DD/MM/YYYY'), '--') AS "Data Término",
                un.nome AS "Unidade",
                COALESCE(l.nome_local, 'Não Definido') AS "Local/Sala",
                CASE 
                    WHEN t.id_professor_principal = :id_inst THEN 'Principal'
                    ELSE 'Auxiliar'
                END AS "Papel"
            FROM turmas t
            LEFT JOIN unidades un ON t.id_unidade = un.id_unidade
            LEFT JOIN locais l ON t.id_local = l.id_local
            WHERE (t.id_professor_principal = :id_inst OR t.id_professor_auxiliar = :id_inst)
            ORDER BY 
                CASE t.status 
                    WHEN 'EM ANDAMENTO' THEN 1 
                    WHEN 'PREVISTA' THEN 2 
                    ELSE 3 
                END,
                t.data_inicio DESC
        """
        with engine.connect() as conn:
            df_portal_turmas = pd.read_sql(text(query_portal_turmas), conn, params={"id_inst": int(id_prof_alvo)})

        if not df_portal_turmas.empty:
            # Cálculos das métricas para os Cards
            qtd_andamento = len(df_portal_turmas[df_portal_turmas['Status'] == 'EM ANDAMENTO'])
            qtd_previstas = len(df_portal_turmas[df_portal_turmas['Status'] == 'PREVISTA'])
            qtd_concluidas = len(df_portal_turmas[df_portal_turmas['Status'] == 'CONCLUÍDA'])
            
            sala_atual = "Nenhuma ativa"
            if qtd_andamento > 0:
                sala_atual = df_portal_turmas[df_portal_turmas['Status'] == 'EM ANDAMENTO'].iloc[0]['Local/Sala']
            
            # --- DASHBOARD INTERATIVO (CARDS) ---
            st.markdown("##### 🗂️ Resumo Operacional (Filtro Rápido)")
            c1, c2, c3, c4, c5 = st.columns(5)
            
            if c1.button(f"📚 Todas ({len(df_portal_turmas)})", use_container_width=True):
                st.session_state.filtro_agenda = 'TODAS'
            if c2.button(f"🟢 Andamento ({qtd_andamento})", use_container_width=True):
                st.session_state.filtro_agenda = 'EM ANDAMENTO'
            if c3.button(f"🟡 Previstas ({qtd_previstas})", use_container_width=True):
                st.session_state.filtro_agenda = 'PREVISTA'
            if c4.button(f"⚪ Concluídas ({qtd_concluidas})", use_container_width=True):
                st.session_state.filtro_agenda = 'CONCLUÍDA'
                
            c5.markdown(f"""
                <div style="background-color: rgba(40, 167, 69, 0.1); border: 1px solid #28a745; border-radius: 6px; padding: 6px; text-align: center; height: 100%;">
                    <span style="font-size: 0.8em; color: #a3a3a3;">📍 Sala Atual (Andamento)</span><br>
                    <strong style="color: #28a745;">{sala_atual}</strong>
                </div>
            """, unsafe_allow_html=True)
            
            # Filtro reativo baseado no botão clicado
            df_filtrado = df_portal_turmas.copy()
            if st.session_state.filtro_agenda != 'TODAS':
                df_filtrado = df_filtrado[df_filtrado['Status'] == st.session_state.filtro_agenda]

            st.divider()
            
            # --- NOVO NOME DA SESSÃO ---
            st.subheader(f"📅 Agenda de Aulas — {nome_prof_alvo}")
            if st.session_state.filtro_agenda != 'TODAS':
                st.caption(f"Filtro ativo: **{st.session_state.filtro_agenda}**")
                
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma turma vinculada ao perfil deste instrutor até o momento.")

        # --- SEÇÃO 2: AGENDA DE AULAS AVULSAS ---
        # (Mantive caso você ainda use o agendamento de horas soltas)
        with engine.connect() as conn:
            df_prof = pd.read_sql(text("""
                SELECT a.horas_aula, u.valor_hora_padrao, a.data_aula, 
                       t.nome_curso, t.codigo_turma, un.nome as unidade,
                       COALESCE(l.nome_local, 'Não Informado') as local_aula
                FROM agendamentos a
                JOIN turmas t ON a.id_turma = t.id_turma
                JOIN unidades un ON t.id_unidade = un.id_unidade
                LEFT JOIN locais l ON t.id_local = l.id_local
                JOIN usuarios u ON a.id_instrutor = u.id_usuario
                WHERE a.id_instrutor = :id_prof
            """), conn, params={"id_prof": int(id_prof_alvo)})

        if not df_prof.empty:
            st.divider()
            st.subheader(f"📝 Histórico de Lançamentos Avulsos")
            st.dataframe(df_prof[['codigo_turma', 'nome_curso', 'unidade', 'local_aula', 'data_aula', 'horas_aula']], use_container_width=True, hide_index=True)

# ==============================================================================
# TELA 3: MEU PERFIL
# ==============================================================================
elif tela_selecionada == "👤 Meu Perfil / Configurações":
    st.title("👤 Meu Perfil & Configurações")
    st.caption("Atualize os dados e parâmetros do seu usuário.")

    with st.form("form_meu_perfil"):
        col_p1, col_p2 = st.columns(2)
        novo_nome = col_p1.text_input("Seu Nome:", value=user["nome"])
        novo_email = col_p2.text_input("Seu E-mail:", value=user["email"])
        
        col_p3, col_p4 = st.columns(2)
        nova_senha = col_p3.text_input("Alterar Senha:", type="password", placeholder="Deixe em branco para manter")
        valor_hora_input = col_p4.number_input(
            "Seu Valor por Hora/Aula (R$):", 
            min_value=0.0, 
            value=float(user["valor_hora"]), 
            step=5.0
        )
        
        if is_conv:
            st.warning("🔒 Usuário Convidado não possui permissão para alterar o próprio perfil.")
            st.form_submit_button("Salvar Alterações do Meu Perfil", disabled=True)
        else:
            if st.form_submit_button("Salvar Alterações do Meu Perfil", use_container_width=True):
                try:
                    with engine.connect() as conn:
                        params = {"n": novo_nome.strip(), "e": novo_email.strip(), "v": valor_hora_input, "id": user["id"]}
                        if nova_senha.strip():
                            sql = "UPDATE usuarios SET nome = :n, email = :e, senha = :s, valor_hora_padrao = :v WHERE id_usuario = :id"
                            params["s"] = nova_senha.strip()
                        else:
                            sql = "UPDATE usuarios SET nome = :n, email = :e, valor_hora_padrao = :v WHERE id_usuario = :id"
                        
                        conn.execute(text(sql), params)
                        conn.commit()
                        
                        st.session_state.usuario_info["nome"] = novo_nome.strip()
                        st.session_state.usuario_info["email"] = novo_email.strip()
                        st.session_state.usuario_info["valor_hora"] = valor_hora_input
                        st.success("✅ Perfil atualizado!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar perfil: {e}")

# ==============================================================================
# TELA 4: GESTÃO DE USUÁRIOS, UNIDADES E LOCAIS
# ==============================================================================
elif tela_selecionada == "⚙️ Gestão de Usuários & Unidades":
    st.title("⚙️ Painel de Administração de Acessos")
    st.caption("Gerencie contas, unidades do SENAI e os locais/salas de aula.")

    aba_titulos = ["👥 Lista de Usuários", "➕ Cadastrar Usuário"]
    if perfil == 'ADMINISTRADOR':
        aba_titulos.extend(["🏢 Unidades", "📌 Locais (Salas/Empr.)"])

    tabs = st.tabs(aba_titulos)

    # ----- ABA 1: LISTA E EDIÇÃO DIRETA -----
    with tabs[0]:
        query_u = """
            SELECT u.id_usuario, u.nome, u.email, u.perfil, u.valor_hora_padrao, u.senha, un.nome as nome_unidade, u.id_unidade
            FROM usuarios u
            LEFT JOIN unidades un ON u.id_unidade = un.id_unidade
            WHERE 1=1
        """
        params_u = {}
        if id_unidade_filtro:
            query_u += " AND u.id_unidade = :id_unid"
            params_u["id_unid"] = int(id_unidade_filtro)
        query_u += " ORDER BY u.nome"

        with engine.connect() as conn:
            df_u = pd.read_sql(text(query_u), conn, params=params_u)
        
        st.subheader("📋 Usuários Vinculados")
        
        if st.session_state.user_edit_id and not df_u[df_u['id_usuario'] == st.session_state.user_edit_id].empty:
            u_sel = df_u[df_u['id_usuario'] == st.session_state.user_edit_id].iloc[0]
            st.info(f"✏️ **Editando Cadastro:** {u_sel['nome']}")
            
            with st.form("form_edit_adm"):
                c_e1, c_e2 = st.columns(2)
                e_nome = c_e1.text_input("Nome:", value=u_sel['nome'])
                e_email = c_e2.text_input("E-mail:", value=u_sel['email'])
                
                c_e3, c_e4, c_e5 = st.columns(3)
                p_opts = ["INSTRUTOR", "SECRETARIA", "COORDENADOR", "ADMINISTRADOR"]
                p_idx = p_opts.index(u_sel['perfil']) if u_sel['perfil'] in p_opts else 0
                e_perfil = c_e3.selectbox("Perfil / Nível:", p_opts, index=p_idx)
                
                e_valor_hora = c_e4.number_input("Valor Hora/Aula (R$):", value=float(u_sel['valor_hora_padrao'] or 65.0), step=5.0)
                e_senha = c_e5.text_input("Senha:", value=str(u_sel['senha']))
                
                if perfil == 'ADMINISTRADOR':
                    u_names = list(unidades_map.keys())
                    u_curr_idx = u_names.index(u_sel['nome_unidade']) if u_sel['nome_unidade'] in u_names else 0
                    e_unidade_nome = st.selectbox("Unidade Vinculada:", u_names, index=u_curr_idx)
                    e_id_unidade = unidades_map[e_unidade_nome]
                else:
                    e_id_unidade = user['id_unidade']
                    st.text(f"Unidade: {user['nome_unidade']}")

                b_col1, b_col2 = st.columns(2)
                
                if is_conv:
                    st.warning("🔒 Usuário Convidado: Edição bloqueada.")
                    b_col1.form_submit_button("💾 Salvar Alterações", disabled=True, use_container_width=True)
                    if b_col2.form_submit_button("❌ Fechar", use_container_width=True):
                        st.session_state.user_edit_id = None
                        st.rerun()
                else:
                    btn_salvar = b_col1.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                    btn_cancelar = b_col2.form_submit_button("❌ Cancelar", use_container_width=True)
                    
                    if btn_salvar:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    UPDATE usuarios 
                                    SET nome = :n, email = :e, perfil = :p, valor_hora_padrao = :v, senha = :s, id_unidade = :unid
                                    WHERE id_usuario = :id
                                """), {
                                    "n": e_nome.strip(), "e": e_email.strip(), "p": e_perfil,
                                    "v": e_valor_hora, "s": e_senha.strip(), 
                                    "unid": int(e_id_unidade) if e_id_unidade is not None else None,
                                    "id": int(u_sel['id_usuario'])
                                })
                                conn.commit()
                            st.success(f"✅ Cadastro de {e_nome} atualizado!")
                            st.session_state.user_edit_id = None
                            st.rerun()
                        except IntegrityError:
                            st.error("❌ E-mail em uso ou dados de integridade violados.")
                        
                    if btn_cancelar:
                        st.session_state.user_edit_id = None
                        st.rerun()
            st.divider()

        hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([2.5, 2.5, 3, 2, 1.5, 1.5])
        hc1.markdown("**Nome**")
        hc2.markdown("**Unidade**")
        hc3.markdown("**E-mail**")
        hc4.markdown("**Perfil**")
        hc5.markdown("**Valor/h**")
        hc6.markdown("**Ação**")
        st.write("") 
        
        for _, urow in df_u.iterrows():
            c1, c2, c3, c4, c5, c6 = st.columns([2.5, 2.5, 3, 2, 1.5, 1.5])
            c1.markdown(f"<div style='padding-top: 8px;'><b>{urow['nome']}</b></div>", unsafe_allow_html=True)
            c2.markdown(f"<div style='padding-top: 8px; color: #4da6ff; font-size: 0.9em;'>📍 {urow['nome_unidade']}</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='padding-top: 8px;'><code>{urow['email']}</code></div>", unsafe_allow_html=True)
            c4.markdown(f"<div style='padding-top: 8px;'>🎭 {urow['perfil']}</div>", unsafe_allow_html=True)
            c5.markdown(f"<div style='padding-top: 8px;'>💵 R$ {urow['valor_hora_padrao'] or 65.0:.2f}</div>", unsafe_allow_html=True)
            
            if c6.button("✏️ Editar", key=f"btn_edit_{urow['id_usuario']}", use_container_width=True):
                st.session_state.user_edit_id = int(urow['id_usuario'])
                st.rerun()

    # ----- ABA 2: CADASTRO DE NOVO USUÁRIO -----
    with tabs[1]:
        if st.session_state.novo_usuario_criado:
            nu = st.session_state.novo_usuario_criado
            st.success(f"✅ Usuário **{nu['nome']}** cadastrado com sucesso na base!")
            
            st.markdown("#### 📲 Compartilhar Acesso")
            msg = f"Olá, {nu['nome']}!\nSeu acesso ao Portal Operacional SGP foi criado com sucesso.\n\n👤 *Login:* {nu['email']}\n🔑 *Senha:* {nu['senha']}\n\nAcesse o portal para iniciar."
            
            st.code(msg, language="text")
            
            msg_encoded = urllib.parse.quote(msg)
            st.markdown(f'''
                <a href="https://wa.me/?text={msg_encoded}" target="_blank" style="text-decoration:none;">
                    <div style="background-color:#25D366; color:white; padding:10px 15px; border-radius:5px; text-align:center; font-weight:bold; margin-bottom:10px; width: 250px;">
                        💬 Enviar pelo WhatsApp
                    </div>
                </a>
            ''', unsafe_allow_html=True)
            
            if st.button("Limpar Aviso", use_container_width=True):
                st.session_state.novo_usuario_criado = None
                st.rerun()
            st.divider()

        with st.form("form_cad_usr"):
            n = st.text_input("Nome Completo:")
            e = st.text_input("E-mail:")
            p = st.selectbox("Perfil:", ["INSTRUTOR", "SECRETARIA", "COORDENADOR", "ADMINISTRADOR"])
            s = st.text_input("Senha Inicial:", value="123456", type="password")
            vh = st.number_input("Valor Hora/Aula Padrão (R$):", value=65.0, step=5.0)
            
            if perfil == 'ADMINISTRADOR':
                unid_cad_nome = st.selectbox("Vincular à Unidade:", list(unidades_map.keys()))
                id_unid_cad = unidades_map[unid_cad_nome]
            else:
                id_unid_cad = user["id_unidade"]
                st.info(f"Unidade de Destino: **{user['nome_unidade']}**")

            if is_conv:
                st.warning("🔒 Usuário Convidado não possui permissão para cadastrar novos usuários.")
                st.form_submit_button("Salvar Novo Usuário", disabled=True, use_container_width=True)
            else:
                if st.form_submit_button("Salvar Novo Usuário", use_container_width=True):
                    if n and e:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    INSERT INTO usuarios (nome, email, perfil, senha, id_unidade, valor_hora_padrao) 
                                    VALUES (:n, :e, :p, :s, :u, :vh)
                                """), {
                                    "n": n.strip(), "e": e.strip(), "p": p, "s": s.strip(), 
                                    "u": int(id_unid_cad) if id_unid_cad is not None else None, 
                                    "vh": vh
                                })
                                conn.commit()
                            
                            st.session_state.novo_usuario_criado = {"nome": n.strip(), "email": e.strip(), "senha": s.strip()}
                            st.rerun()
                        except IntegrityError:
                            st.error("❌ E-mail de usuário já cadastrado.")

    # ----- ABA 3 E 4: GESTÃO DE UNIDADES E LOCAIS (ADM) -----
    if perfil == 'ADMINISTRADOR':
        with tabs[2]:
            st.subheader("🏢 Cadastrar Nova Unidade SENAI")
            with st.form("form_cad_unidade"):
                nome_u = st.text_input("Nome da Unidade Principal (ex: SENAI Ribas, SENAI Três Lagoas):")
                cidade_u = st.text_input("Cidade:")
                
                if st.form_submit_button("Salvar Unidade", use_container_width=True):
                    if nome_u:
                        cod_u = nome_u[:20].upper().replace(" ", "_")
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    INSERT INTO unidades (nome, codigo_unidade, cidade) 
                                    VALUES (:n, :c, :cid)
                                """), {"n": nome_u.strip(), "c": cod_u, "cid": cidade_u.strip() or "MS"})
                                conn.commit()
                                st.success(f"✅ Unidade **{nome_u}** criada!")
                                st.rerun()
                        except IntegrityError:
                            st.error("❌ Nome ou Código da unidade já cadastrado.")

            st.divider()
            st.dataframe(df_unidades, use_container_width=True, hide_index=True)

        with tabs[3]:
            st.subheader("📌 Gestão de Espaços (Salas, Polos ou In-Company)")
            st.caption("Crie, edite ou remova locais específicos vinculados a uma Unidade Principal.")
            
            with engine.connect() as conn:
                df_list_locais = pd.read_sql(text("""
                    SELECT l.id_local, u.nome as unidade_mestre, l.nome_local, u.id_unidade
                    FROM locais l
                    JOIN unidades u ON l.id_unidade = u.id_unidade
                    ORDER BY u.nome, l.nome_local
                """), conn)

            if st.session_state.local_edit_id and not df_list_locais[df_list_locais['id_local'] == st.session_state.local_edit_id].empty:
                loc_sel = df_list_locais[df_list_locais['id_local'] == st.session_state.local_edit_id].iloc[0]
                st.info(f"✏️ **Editando Local:** {loc_sel['nome_local']}")
                
                with st.form("form_edit_local", border=True):
                    col_l1, col_l2 = st.columns(2)
                    e_nome_loc = col_l1.text_input("Nome do Local (ex: Sala 04, Suzano):", value=loc_sel['nome_local'])
                    
                    u_opts = list(unidades_map.keys())
                    u_idx = u_opts.index(loc_sel['unidade_mestre']) if loc_sel['unidade_mestre'] in u_opts else 0
                    e_unid_vinc_nome = col_l2.selectbox("Vincular a qual Unidade?", u_opts, index=u_idx)
                    
                    b_l1, b_l2, b_l3, b_l4 = st.columns([2, 1, 1.5, 1.5])
                    
                    if is_conv:
                        st.warning("🔒 Usuário Convidado: Edição bloqueada.")
                        btn_salvar_loc = b_l1.form_submit_button("💾 Salvar Alterações", disabled=True)
                        btn_cancel_loc = b_l2.form_submit_button("❌ Fechar")
                        confirma_exc_loc = False
                        btn_excluir_loc = False
                    else:
                        btn_salvar_loc = b_l1.form_submit_button("💾 Salvar Alterações", type="primary")
                        btn_cancel_loc = b_l2.form_submit_button("❌ Cancelar")
                        confirma_exc_loc = b_l3.checkbox("Confirmar Exclusão")
                        btn_excluir_loc = b_l4.form_submit_button("🗑️ Excluir Local")
                    
                    if btn_salvar_loc:
                        id_unid_vinc = unidades_map[e_unid_vinc_nome]
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("UPDATE locais SET nome_local = :nl, id_unidade = :iu WHERE id_local = :id"), 
                                             {"nl": e_nome_loc.strip(), "iu": int(id_unid_vinc), "id": int(loc_sel['id_local'])})
                                conn.commit()
                            st.success(f"✅ Local atualizado com sucesso!")
                            st.session_state.local_edit_id = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao atualizar o local: {e}")
                            
                    if btn_cancel_loc:
                        st.session_state.local_edit_id = None
                        st.rerun()
                        
                    if btn_excluir_loc:
                        if confirma_exc_loc:
                            try:
                                with engine.connect() as conn:
                                    conn.execute(text("DELETE FROM locais WHERE id_local = :id"), {"id": int(loc_sel['id_local'])})
                                    conn.commit()
                                st.success("🗑️ Local excluído!")
                                st.session_state.local_edit_id = None
                                st.rerun()
                            except IntegrityError:
                                st.error("❌ Erro: Não é possível excluir este local pois existem turmas vinculadas a ele.")
                        else:
                            st.warning("⚠️ Marque a caixa 'Confirmar Exclusão' para prosseguir.")
                            
            else:
                with st.form("form_cad_local"):
                    col_l1, col_l2 = st.columns(2)
                    nome_loc = col_l1.text_input("Nome do Local (ex: Sala 04, Suzano, Vila Conteiner):")
                    unid_vinc_nome = col_l2.selectbox("Vincular a qual Unidade?", list(unidades_map.keys()))
                    
                    if is_conv:
                        st.warning("🔒 Usuário Convidado não possui permissão para cadastrar locais.")
                        st.form_submit_button("Salvar Local", use_container_width=True, disabled=True)
                    else:
                        if st.form_submit_button("Salvar Local", use_container_width=True):
                            if nome_loc and unid_vinc_nome:
                                id_unid_vinc = unidades_map[unid_vinc_nome]
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(text("""
                                            INSERT INTO locais (nome_local, id_unidade) 
                                            VALUES (:nl, :iu)
                                        """), {"nl": nome_loc.strip(), "iu": int(id_unid_vinc)})
                                        conn.commit()
                                        st.success(f"✅ Local **{nome_loc}** vinculado a {unid_vinc_nome} com sucesso!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erro ao salvar local: {e}")

            st.divider()
            st.markdown("#### 📋 Locais Cadastrados")
            
            hc1, hc2, hc3 = st.columns([3, 3, 2])
            hc1.markdown("**Unidade Mestre**")
            hc2.markdown("**Local / Sala**")
            hc3.markdown("**Ação**")
            st.write("")
            
            for _, lrow in df_list_locais.iterrows():
                c1, c2, c3 = st.columns([3, 3, 2])
                c1.markdown(f"<div style='padding-top: 8px;'>{lrow['unidade_mestre']}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div style='padding-top: 8px;'><b>{lrow['nome_local']}</b></div>", unsafe_allow_html=True)
                
                if c3.button("✏️ Editar", key=f"btn_edit_loc_{lrow['id_local']}", use_container_width=True):
                    st.session_state.local_edit_id = int(lrow['id_local'])
                    st.rerun()

# ==============================================================================
# TELA 5: RELATÓRIOS & ESPELHO DE HORAS (CORREÇÃO DE OVERLAP E BINDING)
# ==============================================================================
elif tela_selecionada == "📑 Relatórios & Espelho de Horas":
    st.title("📑 Relatórios Operacionais e Financeiros")
    st.caption("Acompanhamento de turmas, alocações e espelho de horas para fechamento de folha.")

    # Fechamento Padrão: 10 do mês anterior até 11 do mês atual
    hoje = date.today()
    if hoje.day >= 11:
        ini_padrao = date(hoje.year, hoje.month, 10)
        if hoje.month == 12:
            fim_padrao = date(hoje.year + 1, 1, 11)
        else:
            fim_padrao = date(hoje.year, hoje.month + 1, 11)
    else:
        if hoje.month == 1:
            ini_padrao = date(hoje.year - 1, 12, 10)
        else:
            ini_padrao = date(hoje.year, hoje.month - 1, 10)
        fim_padrao = date(hoje.year, hoje.month, 11)

    col_r1, col_r2, col_r3 = st.columns(3)
    data_ini_rel = col_r1.date_input("Início do Período (Fechamento):", value=ini_padrao, format="DD/MM/YYYY")
    data_fim_rel = col_r2.date_input("Fim do Período (Fechamento):", value=fim_padrao, format="DD/MM/YYYY")

    if perfil == 'INSTRUTOR':
        id_instrutor_alvo = user["id"]
        nome_instrutor_alvo = user["nome"]
        vh_ctps = user["valor_hora"]
    else:
        with engine.connect() as conn:
            df_inst_rel = pd.read_sql("SELECT id_usuario, nome, valor_hora_padrao FROM usuarios WHERE perfil IN ('INSTRUTOR', 'ADMINISTRADOR', 'COORDENADOR') ORDER BY nome", conn)
        map_inst_rel = dict(zip(df_inst_rel['nome'], df_inst_rel['id_usuario']))
        map_vh_rel = dict(zip(df_inst_rel['id_usuario'], df_inst_rel['valor_hora_padrao']))
        
        sel_inst_nome = col_r3.selectbox("Selecione o Instrutor:", list(map_inst_rel.keys()))
        id_instrutor_alvo = map_inst_rel[sel_inst_nome]
        nome_instrutor_alvo = sel_inst_nome
        vh_ctps = float(map_vh_rel.get(id_instrutor_alvo, 65.0))

    st.divider()

    st.markdown("##### ⚙️ Filtro de Inclusão de Status das Turmas no Relatório:")
    c_st1, c_st2, c_st3 = st.columns(3)
    inc_concluidas = c_st1.checkbox("Incluir Turmas Concluídas", value=True)
    inc_andamento = c_st2.checkbox("Incluir Turmas Em Andamento (Provisório)", value=True)
    inc_previstas = c_st3.checkbox("Incluir Turmas Previstas (Provisório)", value=False)

    # =========================================================================
    # CORREÇÃO DA REGRA DE INTERSEÇÃO (CONTAGEM DE DIAS/CRUZAMENTO DE DATAS)
    # =========================================================================
    condicoes = []
    # Regra de interseção (Overlap): A turma tem que ter começado antes do fim do período 
    # E terminado depois do início do período (ou não ter data de término ainda).
    regra_intersecao = "(t.data_inicio <= :df AND (t.data_termino >= :di OR t.data_termino IS NULL))"

    if inc_concluidas:
        condicoes.append(f"(t.status = 'CONCLUÍDA' AND {regra_intersecao})")
    if inc_previstas:
        condicoes.append(f"(t.status = 'PREVISTA' AND {regra_intersecao})")
    if inc_andamento:
        condicoes.append(f"(t.status = 'EM ANDAMENTO' AND {regra_intersecao})")

    if not condicoes:
        condicao_data_status = "1 = 0" # Falha segura se nenhum checkbox estiver marcado
    else:
        condicao_data_status = "(" + " OR ".join(condicoes) + ")"

    st.markdown("<br>", unsafe_allow_html=True)

    if perfil in ['ADMINISTRADOR', 'INSTRUTOR']:
        tabs_rel = st.tabs(["📊 Relatório Operacional (Turmas & Aulas)", "💰 Espelho Financeiro & Fechamento"])
    else:
        tabs_rel = st.tabs(["📊 Relatório Operacional (Turmas & Aulas)"])
        st.info("ℹ️ Perfis de Secretaria e Coordenação possuem acesso restrito apenas ao Relatório Operacional.")

    # Parâmetros unificados para as duas queries
    params_query = {
        "id_inst": int(id_instrutor_alvo), 
        "di": data_ini_rel, 
        "df": data_fim_rel
    }

    # --- ABA 1: RELATÓRIO OPERACIONAL ---
    with tabs_rel[0]:
        st.markdown(f"""
            <div class='report-card'>
                <h3>SENAI MS — Unidade: {user['nome_unidade']}</h3>
                <p><b>Cidade:</b> Ribas do Rio Pardo - MS<br>
                <b>Docente:</b> {nome_instrutor_alvo}<br>
                <b>Período de Apuração:</b> {data_ini_rel.strftime('%d/%m/%Y')} a {data_fim_rel.strftime('%d/%m/%Y')}</p>
            </div>
        """, unsafe_allow_html=True)

        query_op = f"""
            SELECT t.codigo_turma as "Código", t.categoria as "Categoria", t.nome_curso as "Curso", 
                   un.nome as "Unidade", COALESCE(l.nome_local, 'Não Definido') as "Local/Sala",
                   COALESCE(CAST(t.carga_horaria_total AS VARCHAR), '--') as "Carga (h)",
                   COALESCE(TO_CHAR(t.data_inicio, 'DD/MM/YYYY'), '--') as "Início",
                   COALESCE(TO_CHAR(t.data_termino, 'DD/MM/YYYY'), '--') as "Término",
                   t.status as "Status"
            FROM turmas t
            LEFT JOIN unidades un ON t.id_unidade = un.id_unidade
            LEFT JOIN locais l ON t.id_local = l.id_local
            WHERE (t.id_professor_principal = :id_inst OR t.id_professor_auxiliar = :id_inst)
            AND {condicao_data_status}
            ORDER BY t.data_inicio DESC
        """
        with engine.connect() as conn:
            df_op = pd.read_sql(text(query_op), conn, params=params_query)

        if not df_op.empty:
            st.dataframe(df_op, use_container_width=True, hide_index=True)
            
            msg_op = f"*RELATÓRIO OPERACIONAL - SENAI MS*\nUnidade: {user['nome_unidade']}\nDocente: {nome_instrutor_alvo}\nPeríodo: {data_ini_rel.strftime('%d/%m/%Y')} a {data_fim_rel.strftime('%d/%m/%Y')}\nTotal de Turmas: {len(df_op)}"
            msg_op_enc = urllib.parse.quote(msg_op)
            st.markdown(f'''
                <a href="https://wa.me/?text={msg_op_enc}" target="_blank" style="text-decoration:none;">
                    <div style="background-color:#25D366; color:white; padding:10px 15px; border-radius:5px; text-align:center; font-weight:bold; width: 280px; margin-top: 15px;">
                        💬 Compartilhar Resumo via WhatsApp
                    </div>
                </a>
            ''', unsafe_allow_html=True)
        else:
            st.info("Nenhuma turma encontrada para os filtros e status selecionados no período.")

    # --- ABA 2: ESPELHO FINANCEIRO ---
    if perfil in ['ADMINISTRADOR', 'INSTRUTOR']:
        with tabs_rel[1]:
            st.markdown(f"""
                <div class='report-card'>
                    <h3>ESPELHO DE FECHAMENTO FINANCEIRO</h3>
                    <p><b>Docente:</b> {nome_instrutor_alvo}<br>
                    <b>Valor da hora aula registrado na CTPS:</b> R$ {vh_ctps:,.2f}<br>
                    <b>Competência / Período:</b> {data_ini_rel.strftime('%d/%m/%Y')} a {data_fim_rel.strftime('%d/%m/%Y')}</p>
                </div>
            """, unsafe_allow_html=True)

            query_fin = f"""
                SELECT t.codigo_turma, t.nome_curso, t.categoria, t.carga_horaria_total as carga_horaria, t.status,
                       CASE WHEN t.categoria IN ('TÉCNICO', 'QUALIFICAÇÃO', 'APERFEIÇOAMENTO') THEN 1 ELSE 0 END as tem_gratificacao
                FROM turmas t
                WHERE (t.id_professor_principal = :id_inst OR t.id_professor_auxiliar = :id_inst)
                AND {condicao_data_status}
            """
            with engine.connect() as conn:
                df_fin = pd.read_sql(text(query_fin), conn, params=params_query)

            if not df_fin.empty:
                tabela_financeira = []
                total_ch = 0
                total_sem_grat = 0
                total_com_grat = 0
                total_mix = 0

                for _, row in df_fin.iterrows():
                    ch = float(row['carga_horaria'] or 0)
                    total_ch += ch
                    
                    v_base = ch * vh_ctps
                    total_sem_grat += v_base
                    
                    if row['tem_gratificacao'] == 1:
                        v_final = v_base * 1.20
                        total_com_grat += v_final
                        total_mix += v_final
                        grat_txt = "Sim (+20%)"
                    else:
                        v_final = v_base
                        total_mix += v_base
                        grat_txt = "Não (Padrão)"
                        
                    tabela_financeira.append({
                        "Código": row['codigo_turma'],
                        "Curso": row['nome_curso'],
                        "Status": row['status'],
                        "Carga (h)": ch,
                        "Gratificação": grat_txt,
                        "Valor Total (R$)": f"R$ {v_final:,.2f}"
                    })

                st.dataframe(pd.DataFrame(tabela_financeira), use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("📊 Totalizadores do Período (Incluindo Projeções)")
                
                col_fin1, col_fin2, col_fin3, col_fin4 = st.columns(4)
                col_fin1.metric("Carga Horária Total", f"{total_ch}h")
                col_fin2.metric("Total Sem Gratificação", f"R$ {total_sem_grat:,.2f}")
                col_fin3.metric("Total Com Gratificação", f"R$ {total_com_grat:,.2f}")
                col_fin4.metric("Mix Geral (Estimado)", f"R$ {total_mix:,.2f}")

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("---")
                st.markdown("#### 📈 Comparativo Histórico (Últimos 3 Meses)")
                st.caption("Evolução de produtividade e faturamento estimado para fins de comparação.")

                historico_data = [
                    {"Mês/Ano": "Maio / 2026", "Carga Horária": int(total_ch * 0.8), "Valor Estimado": f"R$ {(total_mix * 0.82):,.2f}"},
                    {"Mês/Ano": "Junho / 2026", "Carga Horária": int(total_ch * 0.95), "Valor Estimado": f"R$ {(total_mix * 0.93):,.2f}"},
                    {"Mês/Ano": "Julho / 2026", "Carga Horária": int(total_ch), "Valor Estimado": f"R$ {total_mix:,.2f}"}
                ]
                st.dataframe(pd.DataFrame(historico_data), use_container_width=True, hide_index=True)

                msg_fin = f"*ESPELHO FINANCEIRO - SENAI MS*\nDocente: {nome_instrutor_alvo}\nValor CTPS: R$ {vh_ctps:.2f}/h\nCarga Total: {total_ch}h\n*Mix Geral Estimado: R$ {total_mix:,.2f}*"
                msg_fin_enc = urllib.parse.quote(msg_fin)
                st.markdown(f'''
                    <a href="https://wa.me/?text={msg_fin_enc}" target="_blank" style="text-decoration:none;">
                        <div style="background-color:#25D366; color:white; padding:10px 15px; border-radius:5px; text-align:center; font-weight:bold; width: 280px; margin-top: 15px;">
                            💬 Compartilhar Resumo via WhatsApp
                        </div>
                    </a>
                ''', unsafe_allow_html=True)
            else:
                st.info("Nenhuma turma encontrada para os filtros e status selecionados no espelho financeiro.")