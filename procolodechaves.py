import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3

# --- BANCO DE DADOS ---
conn = sqlite3.connect('protocolo_chaves.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    # Tabela de Chaves (Inventário)
    c.execute('''CREATE TABLE IF NOT EXISTS chaves 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  codigo_chave TEXT UNIQUE, 
                  nome_sala TEXT, 
                  status TEXT DEFAULT 'Disponível', 
                  usuario_atual TEXT)''')
    
    # Tabela de Log (Histórico)
    c.execute('''CREATE TABLE IF NOT EXISTS historico_chaves 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  chave_id TEXT, 
                  usuario TEXT, 
                  acao TEXT, 
                  data_hora TIMESTAMP)''')
    
    # Inserção de exemplo para teste (pode remover depois)
    c.execute("INSERT OR IGNORE INTO chaves (codigo_chave, nome_sala) VALUES ('CH-001', 'Lab 04 - Odonto')")
    c.execute("INSERT OR IGNORE INTO chaves (codigo_chave, nome_sala) VALUES ('CH-002', 'Auditório Principal')")
    conn.commit()

init_db()

st.set_page_config(page_title="Protocolo de Chaves", layout="centered")

# --- INTERFACE PRINCIPAL ---
st.title("🔑 Protocolo de Chaves")

# Buscar chaves cadastradas
df_chaves = pd.read_sql("SELECT * FROM chaves", conn)

if not df_chaves.empty:
    # 1. Seleção da Chave
    opcoes = df_chaves.apply(lambda x: f"{x['codigo_chave']} - {x['nome_sala']} ({x['status']})", axis=1).tolist()
    selecionada = st.selectbox("Selecione a Chave:", opcoes)
    
    # Extrair código da chave selecionada
    cod_selecionado = selecionada.split(" - ")[0]
    info_chave = df_chaves[df_chaves['codigo_chave'] == cod_selecionado].iloc[0]

    st.divider()

    # --- LÓGICA DE RETIRADA ---
    if info_chave['status'] == 'Disponível':
        st.subheader("📝 Formulário de Retirada")
        with st.form("form_retirada", clear_on_submit=True):
            nome_pessoa = st.text_input("Nome do Responsável pela Retirada:")
            contato = st.text_input("Telefone/Ramal (Opcional):")
            
            if st.form_submit_button("Confirmar Retirada"):
                if nome_pessoa:
                    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Atualiza status da chave
                    c.execute("UPDATE chaves SET status='Emprestada', usuario_atual=? WHERE codigo_chave=?", 
                              (nome_pessoa, cod_selecionado))
                    
                    # Registra no histórico
                    c.execute("INSERT INTO historico_chaves (chave_id, usuario, acao, data_hora) VALUES (?,?,?,?)",
                              (cod_selecionado, nome_pessoa, 'Retirada', agora))
                    
                    conn.commit()
                    st.success(f"Retirada de {cod_selecionado} registrada para {nome_pessoa}!")
                    st.rerun()
                else:
                    st.warning("Por favor, identifique o responsável.")

    # --- LÓGICA DE DEVOLUÇÃO ---
    else:
        st.warning(f"Esta chave está atualmente com: **{info_chave['usuario_atual']}**")
        if st.button(f"Registrar Devolução de {cod_selecionado}"):
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            usuario_que_devolveu = info_chave['usuario_atual']
            
            # Atualiza status da chave para disponível
            c.execute("UPDATE chaves SET status='Disponível', usuario_atual=NULL WHERE codigo_chave=?", 
                      (cod_selecionado,))
            
            # Registra no histórico
            c.execute("INSERT INTO historico_chaves (chave_id, usuario, acao, data_hora) VALUES (?,?,?,?)",
                      (cod_selecionado, usuario_que_devolveu, 'Devolução', agora))
            
            conn.commit()
            st.success(f"Chave {cod_selecionado} devolvida com sucesso!")
            st.rerun()

else:
    st.info("Nenhuma chave cadastrada no sistema.")

# --- VISUALIZAÇÃO RÁPIDA (OPCIONAL) ---
st.sidebar.subheader("📊 Status Atual")
st.sidebar.dataframe(df_chaves[['codigo_chave', 'status']], hide_index=True)
