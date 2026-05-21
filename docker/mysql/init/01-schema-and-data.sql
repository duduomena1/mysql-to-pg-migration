-- Script de inicialização para MySQL com dados de exemplo
-- Este script será executado automaticamente quando o container MySQL iniciar

USE testdb;

-- Tabela de Departamentos
CREATE TABLE departments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    budget DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela de Funcionários
CREATE TABLE employees (
    id INT PRIMARY KEY AUTO_INCREMENT,
    department_id INT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    hire_date DATE NOT NULL,
    salary DECIMAL(10, 2),
    is_active BOOLEAN DEFAULT TRUE,
    birth_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
    INDEX idx_email (email),
    INDEX idx_department (department_id),
    INDEX idx_hire_date (hire_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela de Projetos
CREATE TABLE projects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    budget DECIMAL(15, 2),
    status ENUM('planning', 'active', 'on_hold', 'completed', 'cancelled') DEFAULT 'planning',
    department_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_dates (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela de Associação Funcionários-Projetos (muitos para muitos)
CREATE TABLE employee_projects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    project_id INT NOT NULL,
    role VARCHAR(100),
    hours_allocated DECIMAL(5, 2),
    start_date DATE NOT NULL,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE KEY uk_employee_project (employee_id, project_id),
    INDEX idx_employee (employee_id),
    INDEX idx_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela de Endereços
CREATE TABLE addresses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT UNIQUE NOT NULL,
    street VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    country VARCHAR(50) DEFAULT 'Brasil',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela de Logs de Auditoria
CREATE TABLE audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    table_name VARCHAR(50) NOT NULL,
    record_id INT NOT NULL,
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    user_id INT,
    old_values JSON,
    new_values JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Inserindo dados de exemplo

-- Departamentos
INSERT INTO departments (name, location, budget) VALUES
('Tecnologia', 'São Paulo', 500000.00),
('Recursos Humanos', 'Rio de Janeiro', 200000.00),
('Financeiro', 'São Paulo', 300000.00),
('Marketing', 'Belo Horizonte', 250000.00),
('Vendas', 'Curitiba', 400000.00),
('Operações', 'Porto Alegre', 350000.00);

-- Funcionários
INSERT INTO employees (department_id, first_name, last_name, email, phone, hire_date, salary, birth_date) VALUES
(1, 'João', 'Silva', 'joao.silva@example.com', '(11) 98765-4321', '2020-01-15', 8500.00, '1990-05-20'),
(1, 'Maria', 'Santos', 'maria.santos@example.com', '(11) 98765-4322', '2019-03-10', 9200.00, '1988-08-15'),
(1, 'Pedro', 'Oliveira', 'pedro.oliveira@example.com', '(11) 98765-4323', '2021-06-01', 7500.00, '1995-12-03'),
(2, 'Ana', 'Costa', 'ana.costa@example.com', '(21) 98765-4324', '2018-09-20', 6500.00, '1992-03-25'),
(2, 'Carlos', 'Ferreira', 'carlos.ferreira@example.com', '(21) 98765-4325', '2020-11-05', 7000.00, '1991-07-10'),
(3, 'Juliana', 'Almeida', 'juliana.almeida@example.com', '(11) 98765-4326', '2017-02-14', 11000.00, '1985-11-30'),
(3, 'Roberto', 'Lima', 'roberto.lima@example.com', '(11) 98765-4327', '2019-08-22', 9500.00, '1987-04-18'),
(4, 'Fernanda', 'Rodrigues', 'fernanda.rodrigues@example.com', '(31) 98765-4328', '2021-01-10', 7200.00, '1993-09-05'),
(4, 'Lucas', 'Martins', 'lucas.martins@example.com', '(31) 98765-4329', '2020-07-15', 6800.00, '1994-02-28'),
(5, 'Patricia', 'Souza', 'patricia.souza@example.com', '(41) 98765-4330', '2018-05-30', 10500.00, '1986-06-12'),
(5, 'Marcos', 'Pereira', 'marcos.pereira@example.com', '(41) 98765-4331', '2019-12-01', 9000.00, '1989-10-22'),
(6, 'Amanda', 'Gomes', 'amanda.gomes@example.com', '(51) 98765-4332', '2020-03-18', 8200.00, '1991-01-15'),
(6, 'Ricardo', 'Barbosa', 'ricardo.barbosa@example.com', '(51) 98765-4333', '2021-09-25', 7800.00, '1992-12-08'),
(1, 'Camila', 'Dias', 'camila.dias@example.com', '(11) 98765-4334', '2022-02-01', 6500.00, '1996-04-20'),
(3, 'Bruno', 'Araújo', 'bruno.araujo@example.com', '(11) 98765-4335', '2021-11-10', 8800.00, '1990-08-30');

-- Projetos
INSERT INTO projects (name, description, start_date, end_date, budget, status, department_id) VALUES
('Sistema ERP', 'Implementação de sistema ERP corporativo', '2023-01-01', '2024-06-30', 800000.00, 'active', 1),
('Portal de RH', 'Desenvolvimento de portal interno de RH', '2023-03-15', '2023-12-31', 150000.00, 'active', 2),
('Migração Cloud', 'Migração de infraestrutura para cloud', '2023-05-01', NULL, 500000.00, 'active', 1),
('Campanha Verão', 'Campanha de marketing para o verão', '2023-11-01', '2024-02-28', 200000.00, 'planning', 4),
('Expansão Regional', 'Abertura de filiais em 5 novas cidades', '2023-07-01', '2024-12-31', 1000000.00, 'active', 5),
('Automação Financeira', 'Automação de processos financeiros', '2023-02-01', '2023-10-31', 250000.00, 'completed', 3),
('Modernização Operacional', 'Modernização dos processos operacionais', '2023-06-01', '2024-03-31', 400000.00, 'active', 6),
('App Mobile', 'Desenvolvimento de aplicativo mobile', '2023-08-01', NULL, 300000.00, 'planning', 1);

-- Associações Funcionários-Projetos
INSERT INTO employee_projects (employee_id, project_id, role, hours_allocated, start_date, end_date) VALUES
(1, 1, 'Tech Lead', 40.00, '2023-01-01', NULL),
(2, 1, 'Senior Developer', 40.00, '2023-01-01', NULL),
(3, 1, 'Developer', 40.00, '2023-06-01', NULL),
(14, 1, 'Junior Developer', 40.00, '2023-08-01', NULL),
(4, 2, 'Project Manager', 30.00, '2023-03-15', NULL),
(5, 2, 'HR Analyst', 25.00, '2023-03-15', NULL),
(1, 3, 'Architect', 20.00, '2023-05-01', NULL),
(2, 3, 'DevOps Engineer', 30.00, '2023-05-01', NULL),
(8, 4, 'Marketing Manager', 40.00, '2023-11-01', NULL),
(9, 4, 'Marketing Analyst', 40.00, '2023-11-01', NULL),
(10, 5, 'Sales Director', 35.00, '2023-07-01', NULL),
(11, 5, 'Account Manager', 40.00, '2023-07-01', NULL),
(6, 6, 'Financial Controller', 40.00, '2023-02-01', '2023-10-31'),
(7, 6, 'Financial Analyst', 40.00, '2023-02-01', '2023-10-31'),
(12, 7, 'Operations Manager', 40.00, '2023-06-01', NULL),
(13, 7, 'Process Analyst', 40.00, '2023-06-01', NULL),
(1, 8, 'Technical Advisor', 10.00, '2023-08-01', NULL),
(3, 8, 'Mobile Developer', 40.00, '2023-09-01', NULL);

-- Endereços
INSERT INTO addresses (employee_id, street, city, state, zip_code, country) VALUES
(1, 'Rua das Flores, 123', 'São Paulo', 'SP', '01234-567', 'Brasil'),
(2, 'Av. Paulista, 456', 'São Paulo', 'SP', '01310-100', 'Brasil'),
(3, 'Rua Augusta, 789', 'São Paulo', 'SP', '01305-100', 'Brasil'),
(4, 'Rua Copacabana, 321', 'Rio de Janeiro', 'RJ', '22070-011', 'Brasil'),
(5, 'Av. Atlântica, 654', 'Rio de Janeiro', 'RJ', '22021-001', 'Brasil'),
(6, 'Rua da Consolação, 987', 'São Paulo', 'SP', '01301-000', 'Brasil'),
(7, 'Av. Faria Lima, 234', 'São Paulo', 'SP', '01452-000', 'Brasil'),
(8, 'Rua da Bahia, 567', 'Belo Horizonte', 'MG', '30160-011', 'Brasil'),
(9, 'Av. Afonso Pena, 890', 'Belo Horizonte', 'MG', '30130-001', 'Brasil'),
(10, 'Rua XV de Novembro, 432', 'Curitiba', 'PR', '80020-310', 'Brasil'),
(11, 'Av. Cândido de Abreu, 765', 'Curitiba', 'PR', '80530-000', 'Brasil'),
(12, 'Rua dos Andradas, 198', 'Porto Alegre', 'RS', '90020-000', 'Brasil'),
(13, 'Av. Borges de Medeiros, 321', 'Porto Alegre', 'RS', '90020-025', 'Brasil'),
(14, 'Rua Oscar Freire, 555', 'São Paulo', 'SP', '01426-001', 'Brasil'),
(15, 'Av. Brigadeiro Faria Lima, 888', 'São Paulo', 'SP', '01451-001', 'Brasil');

-- Logs de Auditoria (exemplos)
INSERT INTO audit_logs (table_name, record_id, action, user_id, new_values) VALUES
('employees', 1, 'INSERT', 1, '{"first_name": "João", "last_name": "Silva", "email": "joao.silva@example.com"}'),
('employees', 2, 'INSERT', 1, '{"first_name": "Maria", "last_name": "Santos", "email": "maria.santos@example.com"}'),
('departments', 1, 'INSERT', 1, '{"name": "Tecnologia", "location": "São Paulo"}'),
('projects', 1, 'INSERT', 1, '{"name": "Sistema ERP", "status": "planning"}'),
('projects', 1, 'UPDATE', 1, '{"status": "active"}');

-- Criando algumas views para exemplo
CREATE VIEW active_employees AS
SELECT 
    e.id,
    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
    e.email,
    d.name AS department_name,
    e.salary,
    e.hire_date
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
WHERE e.is_active = TRUE;

CREATE VIEW project_summary AS
SELECT 
    p.id,
    p.name,
    p.status,
    d.name AS department_name,
    COUNT(ep.employee_id) AS team_size,
    p.budget,
    p.start_date,
    p.end_date
FROM projects p
LEFT JOIN departments d ON p.department_id = d.id
LEFT JOIN employee_projects ep ON p.id = ep.project_id
GROUP BY p.id, p.name, p.status, d.name, p.budget, p.start_date, p.end_date;

-- Adicionar alguns índices adicionais para teste de migração
CREATE INDEX idx_employees_name ON employees(first_name, last_name);
CREATE INDEX idx_projects_budget ON projects(budget);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);

-- Mostrando estatísticas
SELECT 'Departamentos criados' AS tabela, COUNT(*) AS total FROM departments
UNION ALL
SELECT 'Funcionários criados', COUNT(*) FROM employees
UNION ALL
SELECT 'Projetos criados', COUNT(*) FROM projects
UNION ALL
SELECT 'Alocações criadas', COUNT(*) FROM employee_projects
UNION ALL
SELECT 'Endereços criados', COUNT(*) FROM addresses
UNION ALL
SELECT 'Logs de auditoria', COUNT(*) FROM audit_logs;
