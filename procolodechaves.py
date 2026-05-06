import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
conn = sqlite3.connect('protocolo_chaves_v2.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    # Tabela de Chaves (Inventário)
    c.execute('''CREATE TABLE IF NOT EXISTS chaves 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  codigo_chave TEXT UNIQUE, 
                  nome_sala TEXT, 
                  status TEXT DEFAULT 'Disponível', 
                  usuario_atual TEXT)''')
    
    # Tabela de Log com Atendente (Rastreabilidade)
    c.execute('''CREATE TABLE IF NOT EXISTS historico_chaves 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  chave_id TEXT, 
                  usuario_pessoa TEXT, 
                  acao TEXT, 
                  data_hora TIMESTAMP,
                  atendente TEXT)''')
    
    # Tabela de Usuários (Sistema)
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT)')
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('Admin', '12345')")
    conn.commit()

init_db()

# --- INTERFACE ---
st.set_page_config(page_title="Protocolo de Chaves FASICLIN", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_logged' not in st.session_state:
    st.session_state['user_logged'] = ""

# --- BARRA LATERAL (LOGIN) ---
st.sidebar.title('🔐 Acesso Restrito')
if not st.session_state['logged_in']:
    with st.sidebar:
        u_input = st.text_input('Usuário')
        p_input = st.text_input('Senha', type='password')
        if st.button('Entrar'):
            c.execute('SELECT * FROM usuarios WHERE username = ? AND password = ?', (u_input, p_input))
            if c.fetchone():
                st.session_state['logged_in'] = True
                st.session_state['user_logged'] = u_input
                st.rerun()
            else:
                st.error('Credenciais inválidas')
else:
    nome_u = st.session_state.get('user_logged', 'Usuário')
    st.sidebar.success(f"Logado: {nome_u}")
    
    opcoes = ["Movimentação de Chaves"]
    if nome_u == 'Admin':
        opcoes.extend(["Relatório de Uso", "Gerenciar Inventário", "Gestão de Usuários"])
    
    aba = st.sidebar.radio("Navegação", opcoes)
    
    if st.sidebar.button('Sair'):
        st.session_state['logged_in'] = False
        st.rerun()

# --- FLUXO DE TELAS ---
if not st.session_state['logged_in']:
    st.title("🔑 FASICLIN - Protocolo de Chaves")
    st.info("Por favor, realize o login na barra lateral para operar o sistema.")
    st.image("https://fasiclin.heon.com.br/dashboard/logo.png", width=200) # Exemplo de logo

else:
    # 1. MOVIMENTAÇÃO (TÉCNICOS E ADMIN)
    if aba == "Movimentação de Chaves":
        st.title("🔄 Retirada e Devolução")
        df_c = pd.read_sql("SELECT * FROM chaves", conn)
        
        if df_c.empty:
            st.warning("Nenhuma chave cadastrada no inventário.")
        else:
            col_sel, col_status = st.columns([2, 1])
            with col_sel:
                lista = df_c.apply(lambda x: f"{x['codigo_chave']} - {x['nome_sala']}", axis=1).tolist()
                selecao = st.selectbox("Selecione a Chave:", lista)
                cod = selecao.split(" - ")[0]
                info = df_c[df_c['codigo_chave'] == cod].iloc[0]

            with col_status:
                st.metric("Status Atual", info['status'])

            st.divider()

            if info['status'] == 'Disponível':
                st.subheader("📝 Registrar Retirada")
                with st.form("retirada"):
                    pessoa = st.text_input("Nome do Responsável (Professor/Aluno/Técnico):")
                    if st.form_submit_button("Confirmar Saída"):
                        if pessoa:
                            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            atendente = st.session_state['user_logged']
                            # Atualiza Chave
                            c.execute("UPDATE chaves SET status='Emprestada', usuario_atual=? WHERE codigo_chave=?", (pessoa, cod))
                            # Log Histórico[cite: 2]
                            c.execute("INSERT INTO historico_chaves (chave_id, usuario_pessoa, acao, data_hora, atendente) VALUES (?,?,?,?,?)",
                                      (cod, pessoa, 'Retirada', agora, atendente))
                            conn.commit()
                            st.success(f"Chave {cod} entregue a {pessoa}")
                            st.rerun()
            else:
                st.warning(f"Chave em posse de: **{info['usuario_atual']}**")
                if st.button(f"Confirmar Devolução de {cod}"):
                    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    atendente = st.session_state['user_logged']
                    pessoa_devolveu = info['usuario_atual']
                    # Atualiza Chave[cite: 2]
                    c.execute("UPDATE chaves SET status='Disponível', usuario_atual=NULL WHERE codigo_chave=?", (cod,))
                    # Log Histórico[cite: 2]
                    c.execute("INSERT INTO historico_chaves (chave_id, usuario_pessoa, acao, data_hora, atendente) VALUES (?,?,?,?,?)",
                              (cod, pessoa_devolveu, 'Devolução', agora, atendente))
                    conn.commit()
                    st.rerun()

    # 2. RELATÓRIOS (ADMIN)
    elif aba == "Relatório de Uso":
        st.title("📊 Histórico de Movimentações")
        df_h = pd.read_sql("SELECT * FROM historico_chaves ORDER BY data_hora DESC", conn)
        st.dataframe(df_h, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_h.to_excel(writer, index=False)
        st.download_button("📥 Exportar Histórico para Excel", output.getvalue(), "historico_chaves.xlsx")

    # 3. GERENCIAR INVENTÁRIO (ADMIN)
    elif aba == "Gerenciar Inventário":
        st.title("🛠️ Cadastro de Chaves")
        with st.form("cad_chave"):
            c_cod = st.text_input("Código da Chave (Ex: CH-101)")
            c_sala = st.text_input("Nome da Sala/Laboratório")
            if st.form_submit_button("Cadastrar Chave"):
                try:
                    c.execute("INSERT INTO chaves (codigo_chave, nome_sala) VALUES (?,?)", (c_cod, c_sala))
                    conn.commit()
                    st.success("Chave cadastrada!")
                except: st.error("Este código já existe.")

        st.subheader("Chaves Ativas")
        df_resumo = pd.read_sql("SELECT * FROM chaves", conn)
        for _, r in df_resumo.iterrows():
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**{r['codigo_chave']}**")
            c2.write(r['nome_sala'])
            if c3.button("Remover", key=f"del_{r['codigo_chave']}"):
                c.execute("DELETE FROM chaves WHERE codigo_chave=?", (r['codigo_chave'],))
                conn.commit()
                st.rerun()

    # 4. GESTÃO DE USUÁRIOS (ADMIN)
    elif aba == "Gestão de Usuários":
        st.title("👥 Técnicos do Sistema")
        # Reaproveitando a lógica de cadastro de técnicos que já funciona bem
        with st.form("cad_user"):
            nu = st.text_input("Novo Usuário")
            np = st.text_input("Senha", type='password')
            if st.form_submit_button("Criar Acesso"):
                c.execute("INSERT OR IGNORE INTO usuarios VALUES (?,?)", (nu, np))
                conn.commit()
                st.rerun()
