#!/bin/bash

# Script de gerenciamento do ambiente Docker para testes de migração
# Este script facilita operações comuns com o Docker Compose

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  MySQL → PostgreSQL Migration Test Environment${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker não está instalado!"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose não está instalado!"
        exit 1
    fi
    
    print_success "Docker e Docker Compose estão instalados"
}

start_services() {
    print_info "Iniciando os serviços..."
    docker-compose up -d
    
    print_info "Aguardando serviços ficarem prontos..."
    sleep 10
    
    if [ "$(docker-compose ps -q mysql | wc -l)" -eq 1 ] && \
       [ "$(docker-compose ps -q postgres | wc -l)" -eq 1 ]; then
        print_success "Serviços iniciados com sucesso!"
        show_status
    else
        print_error "Erro ao iniciar serviços"
        docker-compose logs
        exit 1
    fi
}

stop_services() {
    print_info "Parando os serviços..."
    docker-compose down
    print_success "Serviços parados"
}

restart_services() {
    print_info "Reiniciando os serviços..."
    docker-compose restart
    sleep 5
    print_success "Serviços reiniciados"
    show_status
}

reset_all() {
    print_info "ATENÇÃO: Isso irá remover TODOS os dados!"
    read -p "Tem certeza? (yes/no): " -r
    echo
    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Parando containers e removendo volumes..."
        docker-compose down -v
        print_success "Ambiente resetado completamente"
        print_info "Execute 'start' para recriar o ambiente"
    else
        print_info "Operação cancelada"
    fi
}

show_status() {
    echo ""
    print_info "Status dos serviços:"
    docker-compose ps
    echo ""
    print_info "Conexões disponíveis:"
    echo "  MySQL:      localhost:3306"
    echo "  PostgreSQL: localhost:5432"
    echo "  Adminer:    http://localhost:8080"
    echo ""
}

show_logs() {
    SERVICE=$1
    if [ -z "$SERVICE" ]; then
        print_info "Mostrando logs de todos os serviços..."
        docker-compose logs -f
    else
        print_info "Mostrando logs de $SERVICE..."
        docker-compose logs -f "$SERVICE"
    fi
}

mysql_shell() {
    print_info "Conectando ao MySQL..."
    docker exec -it mysqlpg-migration-mysql mysql -u testuser -ptestpass testdb
}

postgres_shell() {
    print_info "Conectando ao PostgreSQL..."
    docker exec -it mysqlpg-migration-postgres psql -U testuser -d testdb
}

verify_data() {
    print_info "Verificando dados no MySQL..."
    
    MYSQL_COUNT=$(docker exec mysqlpg-migration-mysql mysql -u testuser -ptestpass testdb -se "
        SELECT 
            (SELECT COUNT(*) FROM departments) as departments,
            (SELECT COUNT(*) FROM employees) as employees,
            (SELECT COUNT(*) FROM projects) as projects,
            (SELECT COUNT(*) FROM addresses) as addresses;
    ")
    
    echo "Registros no MySQL:"
    echo "$MYSQL_COUNT" | awk '{printf "  Departments: %s\n  Employees: %s\n  Projects: %s\n  Addresses: %s\n", $1, $2, $3, $4}'
    echo ""
    
    print_info "Verificando dados no PostgreSQL..."
    POSTGRES_COUNT=$(docker exec mysqlpg-migration-postgres psql -U testuser -d testdb -t -c "
        SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    " 2>/dev/null | tr -d ' ')
    
    if [ -z "$POSTGRES_COUNT" ] || [ "$POSTGRES_COUNT" = "0" ]; then
        print_info "PostgreSQL ainda não tem tabelas (aguardando migração)"
    else
        echo "Tabelas no PostgreSQL: $POSTGRES_COUNT"
    fi
}

show_help() {
    echo "Uso: $0 [comando] [opções]"
    echo ""
    echo "Comandos disponíveis:"
    echo "  start       - Inicia todos os serviços"
    echo "  stop        - Para todos os serviços"
    echo "  restart     - Reinicia todos os serviços"
    echo "  status      - Mostra o status dos serviços"
    echo "  reset       - Para e remove todos os dados (requer confirmação)"
    echo "  logs [svc]  - Mostra logs (todos ou de um serviço específico)"
    echo "  mysql       - Abre shell do MySQL"
    echo "  postgres    - Abre shell do PostgreSQL"
    echo "  verify      - Verifica a quantidade de dados em ambos os bancos"
    echo "  help        - Mostra esta mensagem"
    echo ""
    echo "Exemplos:"
    echo "  $0 start              # Inicia o ambiente"
    echo "  $0 logs mysql         # Mostra logs do MySQL"
    echo "  $0 verify             # Verifica dados"
    echo ""
}

# Main
print_header

case "${1:-help}" in
    start)
        check_docker
        start_services
        verify_data
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    reset)
        reset_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-}"
        ;;
    mysql)
        mysql_shell
        ;;
    postgres)
        postgres_shell
        ;;
    verify)
        verify_data
        ;;
    help|*)
        show_help
        ;;
esac
