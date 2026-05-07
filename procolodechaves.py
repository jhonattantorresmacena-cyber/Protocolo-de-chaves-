import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io
import secrets  # Biblioteca para geração de tokens seguros

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
conn = sqlite3.connect('protocolo_chaves_v3.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    # Adicionada a coluna 'token' para segurança
    c.execute('''CREATE TABLE IF NOT EXISTS chaves 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  codigo_chave TEXT UNIQUE, 
                  nome_sala TEXT, 
                  status TEXT DEFAULT 'Disponível', 
                  usuario_atual TEXT,
                  token TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS historico_chaves 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  chave_id TEXT, 
                  usuario_pessoa TEXT, 
                  acao TEXT, 
                  data_hora TIMESTAMP,
                  atendente TEXT)''')
    
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT)')
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('Admin', '12345')")
    conn.commit()

init_db()

# --- INTERFACE ---
st.set_page_config(page_title="Protocolo de Chaves FASICLIN", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- BARRA LATERAL ---
st.sidebar.title('🔐 Área Administrativa')
if not st.session_state['logged_in']:
    with st.sidebar:
        u_input = st.text_input('Usuário')
        p_input = st.text_input('Senha', type='password')
        if st.button('Acessar Gestão'):
            c.execute('SELECT * FROM usuarios WHERE username = ? AND password = ?', (u_input, p_input))
            if c.fetchone():
                st.session_state['logged_in'] = True
                st.session_state['user_logged'] = u_input
                st.rerun()
            else:
                st.error('Credenciais inválidas')
else:
    st.sidebar.success(f"Logado: {st.session_state['user_logged']}")
    menu_admin = st.sidebar.radio("Navegação", ["Relatório de Uso", "Gerenciar Inventário", "Gestão de Usuários"])
    if st.sidebar.button('Sair'):
        st.session_state['logged_in'] = False
        st.rerun()

# --- TELA PÚBLICA (RETIRADA E DEVOLUÇÃO) ---
if not st.session_state['logged_in']:
    st.title("🔑 FASICLIN - Protocolo de Chaves")
    st.subheader("🔄 Movimentação com Token de Segurança")
    
    df_c = pd.read_sql("SELECT * FROM chaves", conn)
    
    if df_c.empty:
        st.info("Aguardando cadastro de chaves pelo Administrador.")
    else:
        lista = df_c.apply(lambda x: f"{x['codigo_chave']} - {x['nome_sala']} ({x['status']})", axis=1).tolist()
        selecao = st.selectbox("Selecione a Sala/Chave:", lista)
        cod = selecao.split(" - ")[0]
        info = df_c[df_c['codigo_chave'] == cod].iloc[0]

        st.divider()

        # LÓGICA DE RETIRADA
        if info['status'] == 'Disponível':
            st.subheader("📝 Solicitar Retirada")
            with st.form("form_token_retirada"):
                pessoa = st.text_input("Nome do Responsável:")
                if st.form_submit_button("Gerar Token e Retirar"):
                    if pessoa:
                        # GERA TOKEN ÚNICO (Ex: 4E9A21)
                        novo_token = secrets.token_hex(3).upper()
                        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        c.execute("UPDATE chaves SET status='Emprestada', usuario_atual=?, token=? WHERE codigo_chave=?", 
                                  (pessoa, novo_token, cod))
                        c.execute("INSERT INTO historico_chaves (chave_id, usuario_pessoa, acao, data_hora, atendente) VALUES (?,?,?,?,?)",
                                  (cod, pessoa, 'Retirada', agora, 'Auto-Serviço'))
                        conn.commit()
                        
                        st.success(f"Retirada confirmada para {pessoa}!")
                        st.warning(f"⚠️ SEU CÓDIGO DE DEVOLUÇÃO É: **{novo_token}**")
                        st.info("Tire um print desta tela. Você precisará deste código para devolver a chave.")
                    else:
                        st.error("Identifique-se para retirar a chave.")

        # LÓGICA DE DEVOLUÇÃO
        else:
            st.subheader("🔓 Registrar Devolução")
            st.info(f"Esta chave está com: **{info['usuario_atual']}**")
            with st.form("form_token_devolucao"):
                token_input = st.text_input("Insira o Token de Segurança (6 dígitos):", help="Código gerado no momento da retirada")
                if st.form_submit_button("Validar e Devolver"):
                    if token_input == info['token']:
                        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        usuario_que_tinha = info['usuario_atual']
                        
                        c.execute("UPDATE chaves SET status='Disponível', usuario_atual=NULL, token=NULL WHERE codigo_chave=?", (cod,))
                        c.execute("INSERT INTO historico_chaves (chave_id, usuario_pessoa, acao, data_hora, atendente) VALUES (?,?,?,?,?)",
                                  (cod, usuario_que_tinha, 'Devolução', agora, 'Auto-Serviço'))
                        conn.commit()
                        st.success("Token Validado! Chave devolvida com sucesso.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("Token Inválido! Apenas o portador do código de retirada pode realizar a devolução.")

# --- ÁREA ADMINISTRATIVA ---
else:
    if menu_admin == "Relatório de Uso":
        st.title("📊 Auditoria de Chaves")
        df_h = pd.read_sql("SELECT * FROM historico_chaves ORDER BY data_hora DESC", conn)
        st.dataframe(df_h, use_container_width=True)
        
        # Opção de limpar tokens (em caso de perda pelo professor)
        st.divider()
        st.subheader("🔓 Gestão de Contingência")
        df_ativas = pd.read_sql("SELECT codigo_chave, usuario_atual, token FROM chaves WHERE status='Emprestada'", conn)
        if not df_ativas.empty:
            st.write("Lista de chaves fora e seus respectivos tokens:")
            st.table(df_ativas)
        
    elif menu_admin == "Gerenciar Inventário":
        st.title("🛠️ Inventário de Salas")
        with st.form("cad_c"):
            c1, c2 = st.columns(2)
            c_id = c1.text_input("Código (Ex: CH-01)")
            c_nome = c2.text_input("Sala (Ex: Clínica de Odonto)")
            if st.form_submit_button("Adicionar"):
                c.execute("INSERT INTO chaves (codigo_chave, nome_sala) VALUES (?,?)", (c_id, c_nome))
                conn.commit()
                st.rerun()
        
        df_status = pd.read_sql("SELECT codigo_chave, nome_sala, status FROM chaves", conn)
        st.dataframe(df_status, use_container_width=True)

    elif menu_admin == "Gestão de Usuários":
        # (Lógica de gestão de usuários conforme versões anteriores)
        st.title("👥 Gestão de Administradores")
        u = st.text_input("Novo Login")
        p = st.text_input("Senha", type='password')
        if st.button("Salvar Admin"):
            c.execute("INSERT OR IGNORE INTO usuarios VALUES (?,?)", (u, p))
            conn.commit()
            st.success("Novo administrador cadastrado.")
