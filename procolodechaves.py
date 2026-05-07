import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
# Mantendo o banco v2 para consistência com a estrutura de atendente
conn = sqlite3.connect('protocolo_chaves_v2.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('''CREATE TABLE IF NOT EXISTS chaves 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  codigo_chave TEXT UNIQUE, 
                  nome_sala TEXT, 
                  status TEXT DEFAULT 'Disponível', 
                  usuario_atual TEXT)''')
    
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
        st.write("Acesso restrito para relatórios e gestão.")
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
    st.sidebar.success(f"Logado: {st.session_state['user_logged']}")
    menu_admin = st.sidebar.radio("Gestão Avançada", ["Relatório de Uso", "Gerenciar Inventário", "Gestão de Usuários"])
    if st.sidebar.button('Sair'):
        st.session_state['logged_in'] = False
        st.rerun()

# --- CORPO PRINCIPAL ---

# Se NÃO estiver logado ou se estiver logado mas NÃO selecionou uma aba de gestão,
# mostra a tela de Movimentação (Pública e Rápida)
if not st.session_state['logged_in']:
    st.title("🔑 FASICLIN - Protocolo de Chaves")
    st.subheader("🔄 Retirada e Devolução Rápida")
    
    df_c = pd.read_sql("SELECT * FROM chaves", conn)
    
    if df_c.empty:
        st.info("Nenhuma chave cadastrada. O Admin precisa cadastrar as salas no menu lateral.")
    else:
        # Interface de seleção simplificada
        lista = df_c.apply(lambda x: f"{x['codigo_chave']} - {x['nome_sala']} ({x['status']})", axis=1).tolist()
        selecao = st.selectbox("Selecione a Sala/Chave:", lista)
        cod = selecao.split(" - ")[0]
        info = df_c[df_c['codigo_chave'] == cod].iloc[0]

        st.divider()

        if info['status'] == 'Disponível':
            st.subheader("📝 Formulário de Retirada")
            with st.form("retirada_publica", clear_on_submit=True):
                pessoa = st.text_input("Nome do Professor / Responsável:")
                confirmar = st.form_submit_button("Confirmar Retirada")
                
                if confirmar:
                    if pessoa:
                        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # Como é público, o atendente fica como 'Auto-serviço' ou 'Balcão'
                        c.execute("UPDATE chaves SET status='Emprestada', usuario_atual=? WHERE codigo_chave=?", (pessoa, cod))
                        c.execute("INSERT INTO historico_chaves (chave_id, usuario_pessoa, acao, data_hora, atendente) VALUES (?,?,?,?,?)",
                                  (cod, pessoa, 'Retirada', agora, 'Balcão/Público'))
                        conn.commit()
                        st.success(f"Retirada registrada! Chave {cod} está com {pessoa}.")
                        st.balloons()
                        # Aguarda um pouco e recarrega
                        st.rerun()
                    else:
                        st.warning("Por favor, digite seu nome para continuar.")
        else:
            st.warning(f"Atenção: Esta chave está com **{info['usuario_atual']}**")
            if st.button(f"Registrar Devolução da Chave {cod}"):
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                usuario_que_tinha = info['usuario_atual']
                c.execute("UPDATE chaves SET status='Disponível', usuario_atual=NULL WHERE codigo_chave=?", (cod,))
                c.execute("INSERT INTO historico_chaves (chave_id, usuario_pessoa, acao, data_hora, atendente) VALUES (?,?,?,?,?)",
                          (cod, usuario_que_tinha, 'Devolução', agora, 'Balcão/Público'))
                conn.commit()
                st.success(f"Devolução da chave {cod} realizada com sucesso!")
                st.rerun()

# --- TELAS RESTRITAS (APARECEM QUANDO LOGADO) ---
else:
    if menu_admin == "Relatório de Uso":
        st.title("📊 Histórico de Movimentações")
        df_h = pd.read_sql("SELECT * FROM historico_chaves ORDER BY data_hora DESC", conn)
        st.dataframe(df_h, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_h.to_excel(writer, index=False)
        st.download_button("📥 Baixar Excel", output.getvalue(), "historico_chaves.xlsx")

    elif menu_admin == "Gerenciar Inventário":
        st.title("🛠️ Cadastro de Chaves")
        with st.form("cad"):
            c1, c2 = st.columns(2)
            cod_n = c1.text_input("Cód. Chave")
            sala_n = c2.text_input("Nome da Sala")
            if st.form_submit_button("Cadastrar"):
                c.execute("INSERT INTO chaves (codigo_chave, nome_sala) VALUES (?,?)", (cod_n, sala_n))
                conn.commit()
                st.rerun()

        st.subheader("Lista de Chaves")
        df_inv = pd.read_sql("SELECT * FROM chaves", conn)
        st.table(df_inv[['codigo_chave', 'nome_sala', 'status']])

    elif menu_admin == "Gestão de Usuários":
        st.title("👥 Técnicos/Administradores")
        with st.form("user"):
            u = st.text_input("Login")
            p = st.text_input("Senha", type='password')
            if st.form_submit_button("Criar Usuário"):
                c.execute("INSERT OR IGNORE INTO usuarios VALUES (?,?)", (u, p))
                conn.commit()
                st.rerun()
