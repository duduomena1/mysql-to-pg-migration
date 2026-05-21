#!/bin/bash
# Script para facilitar o uso da aplicação

echo "🚀 MySQL → PostgreSQL Migration Tool"
echo "======================================"
echo ""
echo "Escolha uma opção:"
echo "1) Instalar dependências (poetry install)"
echo "2) Rodar Streamlit (nova interface)"
echo "3) Rodar Flask (interface antiga)"
echo "4) Rodar ambos em paralelo"
echo "5) Sair"
echo ""
read -p "Digite sua escolha [1-5]: " choice

case $choice in
    1)
        echo "📦 Instalando dependências..."
        poetry install
        echo "✅ Instalação concluída!"
        ;;
    2)
        LOCAL_IP=$(hostname -I | awk '{print $1}')
        echo "🎈 Iniciando Streamlit..."
        echo "Acesso local: http://localhost:8501"
        echo "Acesso remoto: http://$LOCAL_IP:8501"
        poetry run streamlit run app_streamlit.py --server.address=0.0.0.0 --server.port=8501
        ;;
    3)
        LOCAL_IP=$(hostname -I | awk '{print $1}')
        echo "🌶️ Iniciando Flask..."
        echo "Acesso local: http://localhost:5005"
        echo "Acesso remoto: http://$LOCAL_IP:5005"
        poetry run python app.py
        ;;
    4)
        LOCAL_IP=$(hostname -I | awk '{print $1}')
        echo "🔄 Iniciando ambos os servidores..."
        echo "Flask local: http://localhost:5005"
        echo "Flask remoto: http://$LOCAL_IP:5005"
        echo "Streamlit local: http://localhost:8501"
        echo "Streamlit remoto: http://$LOCAL_IP:8501"
        echo ""
        # Abrir em processos separados
        poetry run python app.py &
        FLASK_PID=$!
        poetry run streamlit run app_streamlit.py --server.address=0.0.0.0 --server.port=8501 &
        STREAMLIT_PID=$!
        
        echo ""
        echo "✅ Servidores rodando!"
        echo "Pressione CTRL+C para parar ambos"
        
        # Aguardar e capturar CTRL+C
        trap "kill $FLASK_PID $STREAMLIT_PID; exit" INT
        wait
        ;;
    5)
        echo "👋 Até logo!"
        exit 0
        ;;
    *)
        echo "❌ Opção inválida"
        exit 1
        ;;
esac
