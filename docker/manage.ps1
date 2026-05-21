# Script de gerenciamento do ambiente Docker para testes de migração (PowerShell)
# Este script facilita operações comuns com o Docker Compose no Windows

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    
    [Parameter(Position=1)]
    [string]$Service = ""
)

$ErrorActionPreference = "Stop"

function Print-Header {
    Write-Host "================================================" -ForegroundColor Blue
    Write-Host "  MySQL → PostgreSQL Migration Test Environment" -ForegroundColor Blue
    Write-Host "================================================" -ForegroundColor Blue
    Write-Host ""
}

function Print-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Print-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Print-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Yellow
}

function Check-Docker {
    try {
        $null = Get-Command docker -ErrorAction Stop
        $null = Get-Command docker-compose -ErrorAction Stop
        Print-Success "Docker e Docker Compose estão instalados"
        return $true
    }
    catch {
        Print-Error "Docker ou Docker Compose não está instalado!"
        return $false
    }
}

function Start-Services {
    Print-Info "Iniciando os serviços..."
    docker-compose up -d
    
    Print-Info "Aguardando serviços ficarem prontos..."
    Start-Sleep -Seconds 10
    
    $mysqlRunning = docker-compose ps -q mysql
    $postgresRunning = docker-compose ps -q postgres
    
    if ($mysqlRunning -and $postgresRunning) {
        Print-Success "Serviços iniciados com sucesso!"
        Show-Status
        Verify-Data
    }
    else {
        Print-Error "Erro ao iniciar serviços"
        docker-compose logs
        exit 1
    }
}

function Stop-Services {
    Print-Info "Parando os serviços..."
    docker-compose down
    Print-Success "Serviços parados"
}

function Restart-Services {
    Print-Info "Reiniciando os serviços..."
    docker-compose restart
    Start-Sleep -Seconds 5
    Print-Success "Serviços reiniciados"
    Show-Status
}

function Reset-All {
    Print-Info "ATENÇÃO: Isso irá remover TODOS os dados!"
    $confirmation = Read-Host "Tem certeza? (yes/no)"
    
    if ($confirmation -eq "yes") {
        Print-Info "Parando containers e removendo volumes..."
        docker-compose down -v
        Print-Success "Ambiente resetado completamente"
        Print-Info "Execute 'start' para recriar o ambiente"
    }
    else {
        Print-Info "Operação cancelada"
    }
}

function Show-Status {
    Write-Host ""
    Print-Info "Status dos serviços:"
    docker-compose ps
    Write-Host ""
    Print-Info "Conexões disponíveis:"
    Write-Host "  MySQL:      localhost:3306"
    Write-Host "  PostgreSQL: localhost:5432"
    Write-Host "  Adminer:    http://localhost:8080"
    Write-Host ""
}

function Show-Logs {
    param([string]$ServiceName)
    
    if ([string]::IsNullOrEmpty($ServiceName)) {
        Print-Info "Mostrando logs de todos os serviços..."
        docker-compose logs -f
    }
    else {
        Print-Info "Mostrando logs de $ServiceName..."
        docker-compose logs -f $ServiceName
    }
}

function Open-MySQLShell {
    Print-Info "Conectando ao MySQL..."
    docker exec -it mysqlpg-migration-mysql mysql -u testuser -ptestpass testdb
}

function Open-PostgresShell {
    Print-Info "Conectando ao PostgreSQL..."
    docker exec -it mysqlpg-migration-postgres psql -U testuser -d testdb
}

function Verify-Data {
    Print-Info "Verificando dados no MySQL..."
    
    $mysqlQuery = @"
SELECT 
    (SELECT COUNT(*) FROM departments) as departments,
    (SELECT COUNT(*) FROM employees) as employees,
    (SELECT COUNT(*) FROM projects) as projects,
    (SELECT COUNT(*) FROM addresses) as addresses;
"@
    
    $mysqlResult = docker exec mysqlpg-migration-mysql mysql -u testuser -ptestpass testdb -se $mysqlQuery
    
    Write-Host "Registros no MySQL:"
    $counts = $mysqlResult -split "`t"
    Write-Host "  Departments: $($counts[0])"
    Write-Host "  Employees: $($counts[1])"
    Write-Host "  Projects: $($counts[2])"
    Write-Host "  Addresses: $($counts[3])"
    Write-Host ""
    
    Print-Info "Verificando dados no PostgreSQL..."
    try {
        $postgresQuery = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
        $postgresCount = docker exec mysqlpg-migration-postgres psql -U testuser -d testdb -t -c $postgresQuery 2>$null
        $postgresCount = $postgresCount.Trim()
        
        if ([string]::IsNullOrEmpty($postgresCount) -or $postgresCount -eq "0") {
            Print-Info "PostgreSQL ainda não tem tabelas (aguardando migração)"
        }
        else {
            Write-Host "Tabelas no PostgreSQL: $postgresCount"
        }
    }
    catch {
        Print-Info "PostgreSQL ainda não tem tabelas (aguardando migração)"
    }
}

function Show-Help {
    Write-Host "Uso: .\manage.ps1 [comando] [opções]"
    Write-Host ""
    Write-Host "Comandos disponíveis:"
    Write-Host "  start       - Inicia todos os serviços"
    Write-Host "  stop        - Para todos os serviços"
    Write-Host "  restart     - Reinicia todos os serviços"
    Write-Host "  status      - Mostra o status dos serviços"
    Write-Host "  reset       - Para e remove todos os dados (requer confirmação)"
    Write-Host "  logs [svc]  - Mostra logs (todos ou de um serviço específico)"
    Write-Host "  mysql       - Abre shell do MySQL"
    Write-Host "  postgres    - Abre shell do PostgreSQL"
    Write-Host "  verify      - Verifica a quantidade de dados em ambos os bancos"
    Write-Host "  help        - Mostra esta mensagem"
    Write-Host ""
    Write-Host "Exemplos:"
    Write-Host "  .\manage.ps1 start              # Inicia o ambiente"
    Write-Host "  .\manage.ps1 logs mysql         # Mostra logs do MySQL"
    Write-Host "  .\manage.ps1 verify             # Verifica dados"
    Write-Host ""
}

# Main
Print-Header

switch ($Command.ToLower()) {
    "start" {
        if (Check-Docker) {
            Start-Services
        }
    }
    "stop" {
        Stop-Services
    }
    "restart" {
        Restart-Services
    }
    "reset" {
        Reset-All
    }
    "status" {
        Show-Status
    }
    "logs" {
        Show-Logs -ServiceName $Service
    }
    "mysql" {
        Open-MySQLShell
    }
    "postgres" {
        Open-PostgresShell
    }
    "verify" {
        Verify-Data
    }
    default {
        Show-Help
    }
}
