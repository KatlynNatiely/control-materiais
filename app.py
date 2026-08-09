import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Gestão", layout="centered")
st.title("Controle de Materiais do Laboratório")

# 1. CRIANDO A CONEXÃO COM O GOOGLE SHEETS VIA GSPREAD
@st.cache_resource
def conectar_gsheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Pega as credenciais direto dos Secrets do Streamlit Cloud ou local
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    spreadsheet_url = creds_dict.pop("spreadsheet")
    # Ajusta o formato da chave privada para evitar erros de PEM
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    # Pega a URL da planilha dos secrets
    return client.open_by_url(spreadsheet_url)

try:
    sh = conectar_gsheets()
except Exception as e:
    st.error(f"❌ Erro ao conectar com o Google Sheets: {e}")
    st.stop()

# 2. FUNÇÃO PARA CARREGAR OS DADOS DA NUVEM
def carregar_dados():
    try:
        ws_estoque = sh.worksheet("Estoque")
        ws_retiradas = sh.worksheet("Retiradas")
        ws_pagamentos = sh.worksheet("Pagamentos")
        
        st.session_state.estoque = pd.DataFrame(ws_estoque.get_all_records())
        st.session_state.hist_retiradas = pd.DataFrame(ws_retiradas.get_all_records())
        st.session_state.hist_pagamentos = pd.DataFrame(ws_pagamentos.get_all_records())
    except Exception:
        # Se as abas estiverem vazias ou com cabeçalho
        st.session_state.estoque = pd.DataFrame(columns=['Material', 'Unidade', 'Preço Unitário (R$)', 'Qtd em Estoque'])
        st.session_state.hist_retiradas = pd.DataFrame(columns=['Data', 'Aluno', 'Material', 'Qtd Retirada', 'Valor (R$)'])
        st.session_state.hist_pagamentos = pd.DataFrame(columns=['Data', 'Aluno', 'Valor Pago (R$)'])

    if st.session_state.estoque.empty:
        st.session_state.estoque = pd.DataFrame(columns=['Material', 'Unidade', 'Preço Unitário (R$)', 'Qtd em Estoque'])
    if st.session_state.hist_retiradas.empty:
        st.session_state.hist_retiradas = pd.DataFrame(columns=['Data', 'Aluno', 'Material', 'Qtd Retirada', 'Valor (R$)'])
    if st.session_state.hist_pagamentos.empty:
        st.session_state.hist_pagamentos = pd.DataFrame(columns=['Data', 'Aluno', 'Valor Pago (R$)'])

# 3. FUNÇÃO PARA SALVAR OS DADOS NA NUVEM
def salvar_banco():
    try:
        def atualizar_aba(nome_aba, df):
            try:
                ws = sh.worksheet(nome_aba)
            except:
                ws = sh.add_worksheet(title=nome_aba, rows="100", cols="20")
            ws.clear()
            dados = [df.columns.tolist()] + df.fillna("").values.tolist()
            ws.update(dados)

        atualizar_aba("Estoque", st.session_state.estoque)
        atualizar_aba("Retiradas", st.session_state.hist_retiradas)
        atualizar_aba("Pagamentos", st.session_state.hist_pagamentos)
    except Exception as e:
        st.error(f"Erro ao salvar na nuvem: {e}")

# Executa o carregamento apenas na primeira vez que a página abre
if 'dados_carregados' not in st.session_state:
    carregar_dados()
    st.session_state.dados_carregados = True

# 4. VARIÁVEIS DE LOGIN
if 'admin_logado' not in st.session_state:
    st.session_state.admin_logado = False
if 'senha_admin' not in st.session_state:
    st.session_state.senha_admin = '123'
if 'modo_recuperacao' not in st.session_state:
    st.session_state.modo_recuperacao = False

# 5. MENU PRINCIPAL
aba_retirar, aba_admin, aba_historicos = st.tabs(["Registrar Retirada", "⚙️ Editar Estoque", "Históricos e Caixa"])

# ABA 1: RETIRADA
with aba_retirar:
    st.subheader("Nova Retirada")
    
    if st.session_state.estoque.empty:
        st.warning("⚠️ O estoque está vazio! É necessário cadastrar os primeiros materiais.")
    else:
        aluno = st.text_input("Nome:")
        
        lista_materiais = st.session_state.estoque['Material'].dropna().unique().tolist()
        
        if not lista_materiais:
             st.warning("⚠️ Os materiais não estão com o nome preenchido. Avise o Administrador.")
        else:
            material_escolhido = st.selectbox("Selecione o Material:", lista_materiais)
            
            info_material = st.session_state.estoque[st.session_state.estoque['Material'] == material_escolhido].iloc[0]
            unidade = str(info_material['Unidade']).strip()
            preco = info_material['Preço Unitário (R$)']
            
            try:
                preco_formatado = float(preco)
                st.caption(f"ℹ️ Preço atual: R$ {preco_formatado:.2f} por {unidade}")
            except:
                preco_formatado = 0.0
                st.caption("ℹ️ Preço inválido no cadastro. Avise o administrador.")
            
            if unidade.lower() in ['unidades', 'unidade', 'und', 'peças', 'peça']:
                quantidade = st.number_input(f"Quantidade ({unidade}):", min_value=1, step=1)
            else:
                quantidade = st.number_input(f"Quantidade ({unidade}):", min_value=0.1, step=0.1)
            
            if st.button("Confirmar Retirada", type="primary"):
                idx_material = st.session_state.estoque.index[st.session_state.estoque['Material'] == material_escolhido][0]
                
                try:
                    qtd_atual = float(st.session_state.estoque.at[idx_material, 'Qtd em Estoque'])
                except:
                    qtd_atual = 0.0
                
                if not aluno:
                    st.error("❌ Por favor, preencha o nome do aluno.")
                elif quantidade <= 0:
                    st.error("❌ A quantidade deve ser maior que zero.")
                elif quantidade > qtd_atual:
                    st.error(f"❌ Estoque insuficiente! Você pediu {quantidade}, mas só temos {qtd_atual} disponíveis.")
                elif preco_formatado <= 0:
                    st.error("❌ Este item está com o preço zerado. Avise o administrador.")
                else:
                    valor_total = quantidade * preco_formatado
                    
                    nova_retirada = pd.DataFrame([{
                        'Data': datetime.now().strftime("%d/%m/%Y %H:%M"),
                        'Aluno': aluno,
                        'Material': material_escolhido,
                        'Qtd Retirada': quantidade,
                        'Valor (R$)': round(valor_total, 2)
                    }])
                    st.session_state.hist_retiradas = pd.concat([st.session_state.hist_retiradas, nova_retirada], ignore_index=True)
                    
                    st.session_state.estoque.at[idx_material, 'Qtd em Estoque'] = qtd_atual - quantidade
                    
                    salvar_banco()
                    
                    st.success(f"✅ Registrado! {quantidade} {unidade} de {material_escolhido} para {aluno}. Valor total: R$ {valor_total:.2f}")

# ABA 2: EDITAR ESTOQUE
with aba_admin:
    if not st.session_state.admin_logado:
        if st.session_state.modo_recuperacao:
            st.subheader("🔄 Redefinir Senha")
            st.info("Para criar uma nova senha, digite a palavra de segurança.")
            
            palavra_secreta = st.text_input("Palavra de Segurança:", type="password")
            nova_senha = st.text_input("Nova senha (apenas 3 dígitos):", max_chars=3, type="password")
            
            if st.button("Salvar Nova Senha"):
                if palavra_secreta.lower() == "admin": 
                    if len(nova_senha) == 3 and nova_senha.isdigit():
                        st.session_state.senha_admin = nova_senha
                        st.session_state.modo_recuperacao = False
                        st.success("✅ Senha alterada com sucesso! Faça o login abaixo.")
                        st.rerun()
                    else:
                        st.error("❌ A senha deve conter exatamente 3 números.")
                else:
                    st.error("❌ Palavra de segurança incorreta.")
            
            if st.button("Voltar ao Login"):
                st.session_state.modo_recuperacao = False
                st.rerun()
        else:
            st.subheader("🔒 Acesso Restrito")
            st.write("Insira a senha de administrador para editar o estoque e ver o caixa.")
            
            senha_digitada = st.text_input("Senha (3 dígitos):", max_chars=3, type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Entrar", type="primary"):
                    if senha_digitada == st.session_state.senha_admin:
                        st.session_state.admin_logado = True
                        st.rerun()
                    else:
                        st.error("❌ Senha incorreta.")
            with col2:
                if st.button("Esqueci a senha"):
                    st.session_state.modo_recuperacao = True
                    st.rerun()
    else:
        col_titulo, col_botao = st.columns([0.8, 0.2])
        with col_titulo:
            st.subheader("📦 Gerenciar Materiais")
        with col_botao:
            if st.button("Sair (Logout)"):
                st.session_state.admin_logado = False
                st.rerun()
                
        with st.expander("➕ Adicionar Novo Material", expanded=True):
            with st.form("form_novo_material", clear_on_submit=True):
                col_m1, col_m2 = st.columns(2)
                novo_nome = col_m1.text_input("Nome do Material:")
                nova_unidade = col_m2.selectbox("Unidade:", ["unidades", "metros", "gramas", "litros"])
                
                col_m3, col_m4 = st.columns(2)
                novo_preco = col_m3.number_input("Preço Unitário (R$):", min_value=0.01, step=0.10)
                nova_qtd = col_m4.number_input("Qtd Inicial em Estoque:", min_value=0.0, step=1.0)
                
                if st.form_submit_button("Cadastrar Material"):
                    if novo_nome:
                        novo_item = pd.DataFrame([{
                            'Material': novo_nome, 
                            'Unidade': nova_unidade, 
                            'Preço Unitário (R$)': novo_preco, 
                            'Qtd em Estoque': nova_qtd
                        }])
                        st.session_state.estoque = pd.concat([st.session_state.estoque, novo_item], ignore_index=True)
                        salvar_banco()
                        st.success(f"✅ '{novo_nome}' cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Você precisa preencher o nome do material.")
        
        st.divider()
        st.info("✏️ **Editar ou Apagar:** Clique na tabela para alterar valores ou nomes. Para excluir um item, clique na borda esquerda da linha e aperte a tecla **Delete**.")
        
        estoque_editado = st.data_editor(
            st.session_state.estoque,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_estoque",
            column_config={
                "Preço Unitário (R$)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                "Qtd em Estoque": st.column_config.NumberColumn(min_value=0.0)
            }
        )
        
        if not estoque_editado.equals(st.session_state.estoque):
            st.session_state.estoque = estoque_editado
            salvar_banco()

# ABA 3: HISTÓRICOS E CAIXA
with aba_historicos:
    if not st.session_state.admin_logado:
        st.warning("🔒 Área restrita. Faça login na aba 'Editar Estoque' para acessar o financeiro.")
    else:
        st.subheader("💸 Registrar Pagamento")
        col1, col2 = st.columns(2)
        with col1:
            aluno_pagante = st.text_input("Nome de quem está pagando:")
        with col2:
            valor_pago = st.number_input("Valor Recebido (R$):", min_value=0.01, step=0.50, format="%.2f")
            
        if st.button("Salvar Pagamento", type="primary"):
            if aluno_pagante:
                aluno_retiradas = st.session_state.hist_retiradas[st.session_state.hist_retiradas['Aluno'] == aluno_pagante]
                
                if aluno_retiradas.empty:
                    st.error(f"❌ Erro: O aluno '{aluno_pagante}' não possui nenhum registro de retirada no sistema.")
                else:
                    total_gasto_aluno = aluno_retiradas['Valor (R$)'].sum()
                    
                    aluno_pagamentos = st.session_state.hist_pagamentos[st.session_state.hist_pagamentos['Aluno'] == aluno_pagante]
                    total_pago_aluno = aluno_pagamentos['Valor Pago (R$)'].sum() if not aluno_pagamentos.empty else 0.0
                    
                    divida_atual = round(total_gasto_aluno - total_pago_aluno, 2)
                    valor_pago_arredondado = round(valor_pago, 2)
                    
                    if divida_atual <= 0:
                        st.error(f"❌ O aluno '{aluno_pagante}' não possui dívidas pendentes (Saldo: R$ 0.00).")
                    elif valor_pago_arredondado > divida_atual:
                        st.error(f"❌ Valor inválido! A dívida atual de '{aluno_pagante}' é de apenas R$ {divida_atual:.2f}. Você tentou registrar R$ {valor_pago_arredondado:.2f}.")
                    else:
                        novo_pag = pd.DataFrame([{
                            'Data': datetime.now().strftime("%d/%m/%Y %H:%M"),
                            'Aluno': aluno_pagante,
                            'Valor Pago (R$)': valor_pago_arredondado
                        }])
                        st.session_state.hist_pagamentos = pd.concat([st.session_state.hist_pagamentos, novo_pag], ignore_index=True)
                        salvar_banco()
                        st.success(f"✅ Pagamento de R$ {valor_pago_arredondado:.2f} salvo! Dívida restante: R$ {divida_atual - valor_pago_arredondado:.2f}")
                
        st.divider()
        
        st.subheader("📜 Histórico de Retiradas")
        retiradas_editadas = st.data_editor(
            st.session_state.hist_retiradas,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_retiradas" 
        )
        if not retiradas_editadas.equals(st.session_state.hist_retiradas):
            st.session_state.hist_retiradas = retiradas_editadas
            salvar_banco()
        
        st.subheader("📜 Histórico de Pagamentos")
        pagamentos_editados = st.data_editor(
            st.session_state.hist_pagamentos,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_pagamentos"
        )
        if not pagamentos_editados.equals(st.session_state.hist_pagamentos):
            st.session_state.hist_pagamentos = pagamentos_editados
            salvar_banco()

        st.divider()

        st.subheader("⚠️ Resumo de Saldos (Quem deve o quê)")
        
        if not st.session_state.hist_retiradas.empty:
            total_gasto = st.session_state.hist_retiradas.groupby('Aluno')['Valor (R$)'].sum().reset_index()
            total_gasto.rename(columns={'Valor (R$)': 'Total Gasto (R$)'}, inplace=True)
        else:
            total_gasto = pd.DataFrame(columns=['Aluno', 'Total Gasto (R$)'])
            
        if not st.session_state.hist_pagamentos.empty:
            total_pago = st.session_state.hist_pagamentos.groupby('Aluno')['Valor Pago (R$)'].sum().reset_index()
        else:
            total_pago = pd.DataFrame(columns=['Aluno', 'Valor Pago (R$)'])
            
        if not total_gasto.empty or not total_pago.empty:
            resumo = pd.merge(total_gasto, total_pago, on='Aluno', how='outer').fillna(0)
            
            if 'Total Gasto (R$)' not in resumo.columns:
                resumo['Total Gasto (R$)'] = 0.0
            if 'Valor Pago (R$)' not in resumo.columns:
                resumo['Valor Pago (R$)'] = 0.0
                
            resumo['Falta Pagar (R$)'] = resumo['Total Gasto (R$)'] - resumo['Valor Pago (R$)']
            
            st.dataframe(resumo.style.format(precision=2), use_container_width=True)
        else:
            st.info("Nenhuma movimentação registrada ainda.")
