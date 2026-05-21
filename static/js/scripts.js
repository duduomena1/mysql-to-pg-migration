const socket = io();
let form = null;
let input = null;
let messages = null;
let result_log = null;
let currentTab = null;

let intermediate_file_progress = null;
let migrate_progress = null;


socket.on('status', (status) => {
   if (status != null){
        //console.log(status);
        update_mysql_card(status.mysql);
        update_postgres_card(status.postgres);
        updateInputs(status.configure);
        update_metadata(status.tables);
    }
});

socket.on('log', (log) => {
    if (log != null){
        // Encontra o container de logs da aba ativa
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab) {
            const activeTabId = activeTab.id;
            const logContainer = activeTab.querySelector('#result_log');
            if (logContainer) {
                appendLogLine(logContainer, log.log_level, log.message);
            } else {
                console.error('Container de log não encontrado na aba ativa:', activeTabId);
            }
        } else {
            console.error('Nenhuma aba ativa encontrada!');
        }
    }
 });

socket.on("connect", () => {
    console.log("MY ID: " + socket.id);
});


/* Código antigo da barra de progresso - comentado para usar Rich Progress no backend
socket.on("update_progress", (progress) => {
    updateProgressBar(intermediate_file_progress, progress.file_name, progress.intermediate_file_progress, progress.total);
    updateProgressBar(migrate_progress, progress.name, progress.migrate_progress, progress.total);
});
*/

// Nova implementação com Rich Progress - espelhando terminal
socket.on("rich_terminal", (data) => {
    console.log("Received rich_terminal event:", data);
    updateRichTerminal(data);
});


socket.on("update_sequence", (table, new_value) => {
    console.log("Table: " + table);
    console.log("New Value: " + new_value);
    
    update_sequence_data(table, new_value)
});


function clickTabEvent(tab){
    currentTab = tab;
    
    console.log(`Mudando para aba: ${tab}`);
    // Container de logs global - não precisa atualizar

    if (tab == "connection") {
        socket.emit('test_connections');
    }
    if (tab == "configure") {
        socket.emit('configure', null);
    }

    if(tab == "conversion"){
        socket.emit('load_metadata', false);
    }

    if (tab == "tables" || tab == "primary-keys" || tab == "constraints" || tab == "indexes" || tab == "tuples" || tab == "sequences") {
        socket.emit('load_metadata', null);
    }
    
    if (tab == "partial") {
        loadTablesForPartial();
    }
}

document.addEventListener("DOMContentLoaded", function() {
    const tabs = document.querySelectorAll('.navbar-link');
    const tabContents = document.querySelectorAll('.tab-content');

    form = document.getElementById('form');
    input = document.getElementById('input');
    messages = document.getElementById('messages');
    result_log = document.getElementById("result_log"); // Container de logs global único
    
    intermediate_file_progress = document.getElementById('intermediate_file_progress');
    migrate_progress = document.getElementById('migrate_progress');
    
    // Inicializa log global como visível (aba Connection é a primeira)
    const globalLog = document.getElementById('global_log_container');
    if (globalLog) {
        globalLog.style.display = 'block';
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            const tabId = this.getAttribute('data-tab');

            clickTabEvent(tabId);
            changeFilter(tabId, tabs);

            const activeTab = document.getElementById(tabId);
            tabContents.forEach(content => {
                content.classList.remove('active');
            });

            tabs.forEach(tab => {
                tab.classList.remove('active');
            });

            activeTab.classList.add('active');
            this.classList.add('active');
            
            // Ajusta posicionamento do container de logs global para aba tuples
            const body = document.body;
            if (tabId === 'tuples') {
                body.classList.add('tuples-active');
            } else {
                body.classList.remove('tuples-active');
            }
            
            // Container de logs global - não precisa atualizar
        });

        if (tab.getAttribute('data-tab') === 'connection') {
            tab.click();
        }
    });
    
    // Container de logs global - já inicializado
    console.log('Container de logs global inicializado:', result_log ? 'OK' : 'ERRO');
});

function BUTTON_migrate_tables() {
    socket.emit('migrate_tables');
}

function BUTTON_migrate_primary_keys() {
    socket.emit('migrate_primary_keys');
}

function BUTTON_generate_migration_order() {
    console.log('Generating migration order based on FK dependencies...');
    socket.emit('generate_migration_order');
}

function BUTTON_migrate_tuples() {
    socket.emit('migrate_tuples');
}

function BUTTON_migrate_constraints() {
    socket.emit('migrate_constraints');
}

function BUTTON_migrate_indexes() {
    socket.emit('migrate_indexes');
}

function BUTTON_migrate_sequences() {
    socket.emit('migrate_sequences');
}



function BUTTON_updateConfiguration() {

    let schema_name = document.getElementById("schema_name").value;
    let postgres_bulk_size = document.getElementById("postgres_bulk_size").value;
    let mysql_batch_size = document.getElementById("mysql_batch_size").value;

    let configData = {
        schema_name: schema_name,
        postgres_bulk_size: parseInt(postgres_bulk_size), 
        mysql_batch_size: parseInt(mysql_batch_size) 
    };

    socket.emit('configure', configData);
}


function BUTTON_load_metadata(mode) { 
    if (mode != null ) {
        // Adiciona mensagem de log quando carregando tabelas na aba conversion
        const logContainer = getActiveLogContainer();
        if (logContainer) {
            appendLogLine(logContainer, "INFO", "🔄 Coletando informações das tabelas do banco de dados...");
        }
        
        socket.emit('load_metadata', true);
    }else{
       
        socket.emit('load_metadata', null);
    }
}


function BUTTON_load_select() { 
    socket.emit('update_table_metadata_select_all'); 
}

function BUTTON_load_deselect() {
    socket.emit('update_table_metadata_deselect_all');
}

function BUTTON_clear_metadata() {
    socket.emit('clear_metadata');
}

function BUTTON_clear_files() {
    socket.emit('clear_files');
}

function BUTTON_clear_database() {
    socket.emit('clear_database');
}


function BUTTON_update_sequence(){
    let tableName = document.getElementById("sequences-table-name");
    let sequence_input = document.getElementById("current_sequence");
    let sequence_value = sequence_input.value

    // if (sequence_value == "" || sequence_value == null) {
    //     sequence_value = "1";
    // }
    socket.emit('handle_sequences', tableName.textContent, sequence_value);
  }

function update_metadata(tables) {
    if (tables == null) {
        return;
    }
    let gridContainer = null 

    if (currentTab == 'configure') {
        gridContainer = document.getElementById('conversion'+"-grid-container");
    }else{
        gridContainer = document.getElementById(currentTab+"-grid-container");
    }
    gridContainer.innerHTML = ""; 
    

    
    console.log("Tables: " + tables.length);

    for (let i = 0; i < tables.length; i++) {
        let item = JSON.parse(tables[i]);
        //console.log(item);
        createNewItem(item, item.name);
    }
    
}

function updateInputs(configData) {
    if (configData == null) {
        return;
    }
    document.getElementById("schema_name").value = configData.schema_name;
    document.getElementById("postgres_bulk_size").value = configData.postgres_bulk_size;
    document.getElementById("mysql_batch_size").value = configData.mysql_batch_size;
}


function update_postgres_card(data) {
    if (data == null) {
        return;
    }
    const card = document.getElementById('postgres-card');
    if (card) {
        const dbname = card.querySelector('#postgres-dbname');
        const user = card.querySelector('#postgres-user');
        const host = card.querySelector('#postgres-host');
        const port = card.querySelector('#postgres-port');
        const error = card.querySelector('#postgres-error');
        
        dbname.textContent = `Database Name: ${data.POSTGRES_DBNAME}`;
        user.textContent = `Username: ${data.POSTGRES_USER}`;
        host.textContent = `Host: ${data.POSTGRES_HOST}`;
        port.textContent = `Port: ${data.POSTGRES_PORT}`;
        
       
        card.style.borderColor = data.connected ? 'green' : 'red';
        
       
        if (data.error) {
            error.textContent = `Error: ${data.error}`;
        } else {
            error.textContent = ''; 
        }
    }
}


function update_mysql_card(data) {
    if (data == null) {
        return;
    }
    const card = document.getElementById('mysql-card');
    if (card) {
        const dbname = card.querySelector('#mysql-dbname');
        const user = card.querySelector('#mysql-user');
        const host = card.querySelector('#mysql-host');
        const port = card.querySelector('#mysql-port');
        const error = card.querySelector('#mysql-error');
        
        dbname.textContent = `Database Name: ${data.MYSQL_DATABASE}`;
        user.textContent = `Username: ${data.MYSQL_USER}`;
        host.textContent = `Host: ${data.MYSQL_HOST}`;
        port.textContent = `Port: ${data.MYSQL_PORT}`;
        
       
        card.style.borderColor = data.connected ? 'green' : 'red';
        
        if (data.error) {
            error.textContent = `Error: ${data.error}`;
        } else {
            error.textContent = ''; 
        }
    }
}

// Retorna o container de logs da aba ativa
function getActiveLogContainer() {
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab) {
        return activeTab.querySelector('#result_log');
    }
    return null;
}

function appendLogLine(log, level, line) {
    if (!log) return; // Proteção contra log container inexistente
    
    let logLine = document.createElement("div");
    logLine.textContent = level + ": " + line;
    log.appendChild(logLine);
    if (level == "ERROR") logLine.style.color = "red"
    if (level == "WARNING") logLine.style.color = "orange"
    //console.log(log.scrollTop);
    //console.log(log.scrollHeight)
    //console.log("-----");
    log.scrollTop = log.scrollHeight;
}

function createNewItem(table, itemId) {
    itemId = itemId + "_" + currentTab;
    let newItem = document.createElement("div");
    newItem.className = "item";
    let name = formatString(table.name);
    let icon = "tables";
    let type = null

    if (currentTab == "tables") {
        icon = "tables_sql";
        type = "table_commited"
        if(table.table_commited){
            icon = "tables_sql_green";
        }
    }

    if (currentTab == "primary-keys") {
        icon = "primary-keys";
        type = "primary_key_commited"
        if(table.primary_key_commited){
            icon = "primary-keys_green";
        }
    }
    
    if (currentTab == "constraints") {
        icon = "constraints";
        type = "constraints_commited"
        if(table.constraints_commited){
            icon = "constraints_green";
        }
    }

    if (currentTab == "indexes") {
        icon = "indexes";
        type = "indexes_commited"
        if(table.indexes_commited){
            icon = "indexes_green";
        }
    }

    if (currentTab == "tuples") {
        icon = "tuples";
        type = "tuples_commited"
        if(table.tuples_commited){
            icon = "tuples_green";
        }
    }


    if (currentTab == "sequences") {
        icon = "sequences";
        if (table.num_sequence >= 0) {
            if(table.sequences_commited){
                icon = "sequences_green";
            }
        } else {
            icon = 'sequences_red';
        }
    }

    let action_button_icon = "remove";

    if (type != null){
        action_button_icon = "reset";
    }

    newItem.innerHTML = `
      <img src="/static/icons/${icon}.png" alt="Table Icon">
      <p style="word-break: break-word;">${name}</p>
      <button class="reset-btn" >
        <img class="reset-btn-img" src="/static/icons/${action_button_icon}.png" alt="reset">
      </button>
    `;
    
    newItem.id = itemId;
    newItem.addEventListener("click", function() {
        console.log("Name: " + table.name);
        console.log("Excluded: " + table.excluded);
        console.log("Table Commited: " + table.table_commited);
        console.log("Primary Key Commited: " + table.primary_key_commited);
        console.log("Constraints Commited: " + table.constraints_commited);
        console.log("Indexes Commited: " + table.indexes_commited);
        console.log("Tuples Commited: " + table.tuples_commited);
        console.log("......................")

        if (currentTab == "conversion") {
            console.log("(conversion) You clicked item: " + itemId);
            console.log(table);
            displayTableInfo(table);
        }

        if(currentTab == "sequences"){
            console.log("(sequences) You clicked item: " + itemId);
            displaySequencesInfo(table);
        }

        if(currentTab == "indexes"){
            console.log("(indexes) You clicked item: " + itemId);
            displayIndexInfo(table);
        }
    });


    let iconImage = newItem.querySelector("img");
    let button = newItem.querySelector("button");

    if (currentTab != "sequences") {
        button.addEventListener("click", function() {

        
            console.log("You clicked to remove item: " + table.name);
            if (table.excluded) {
                table.excluded = false;
            }else {
                table.excluded = true;
            }

            socket.emit('update_table_metadata', {name: table.name, excluded: table.excluded, type: type}); 
            
            
        });

        if (type != null && icon != null && !icon.includes("green")){
            button.style.display = "none";
        }


    }else{
        button.style.display = "none";
    }
    /*
    if (currentTab == "conversion" ||  currentTab == "indexes") {

        button.addEventListener("click", function() {

            if(currentTab == "conversion"){
                console.log("You clicked to remove item: " + table.name);
                if (table.excluded) {
                    table.excluded = false;
                    iconImage.src = "/static/icons/tables.png";
                }else {
                    table.excluded = true;
                    iconImage.src = "/static/icons/tables_red.png";
                }
                socket.emit('update_table_metadata', {name: table.name, excluded: table.excluded}); 
            } 
              
        });
    }else{
        button.style.display = "none";
    }
    */

    if (table.excluded) {
        iconImage.src = "/static/icons/" + icon + "_red.png";
        if (icon != null && icon.includes("green")){
            iconImage.src = "/static/icons/" + icon + ".png";
        }
    }else{
        iconImage.src = "/static/icons/" + icon + ".png";
    }

    let gridContainer = document.getElementById(currentTab+"-grid-container");
    gridContainer.appendChild(newItem);
  }
  

  function formatString(inputString) {
    return inputString;
    
    if (inputString.length > 15) {
      return inputString.substring(0, 15) + "...";
    } else {
      return inputString;
    }
  }


  function displayTableInfo(data) {
    document.getElementById("conversion_table_info").style.display = "block";
    let tableName = document.getElementById("conversion-table-name");
    tableName.textContent = "Table: "+data.name;
    let tableTuples = document.getElementById("conversion-table-tuples");
    tableTuples.textContent = "Number of Tuples: "+data.num_tuples;

    if(data.columns != null)     displayColumns(data.columns);
    if(data.constraints != null) displayConstraints(data.constraints);
    if(data.indexes != null)     displayIndexes(data.indexes);
    if(data.partitions != null)  displayPartitions(data.partitions);
  }

  
  function displayColumns(columns) {
    let tableBody = document.querySelector('#columns-table tbody');
    tableBody.innerHTML = '';
  
    columns.forEach(function(column) {
      let row = document.createElement('tr');
      row.innerHTML = `
        <td>${column.name}</td>
        <td>${column.data_type}</td>
        <td>${column.nullable ? 'Yes' : 'No'}</td>
        <td>${column.default !== null ? column.default : 'None'}</td>
        <td>${column.extra !== null ? column.extra : 'None'}</td>
      `;
      tableBody.appendChild(row);
    });
  }
  
  function displayConstraints(constraints) {
    let tableBody = document.querySelector('#constraints-table tbody');
    tableBody.innerHTML = '';
  
    constraints.forEach(function(constraint) {
      let row = document.createElement('tr');
      row.innerHTML = `
        <td>${constraint.name}</td>
        <td>${constraint.column_name}</td>
        <td>${constraint.referenced_table_schema}</td>
        <td>${constraint.referenced_table_name}</td>
        <td>${constraint.referenced_column_name}</td>
      `;
      tableBody.appendChild(row);
    });
  }

  function displayPartitions(partitions) {
    let tableBody = document.querySelector('#partitions-table tbody');
    tableBody.innerHTML = '';
  
    partitions.forEach(function(partition) {
      let row = document.createElement('tr');
      row.innerHTML = `
        <td>${partition.position}</td>
        <td>${partition.name}</td>
        <td>${partition.method}</td>
        <td>${partition.expression}</td>
        <td>${partition.description}</td>
      `;
      tableBody.appendChild(row);
    });
  }
  
  function displayIndexes(indexes) {
    let tableBody = document.querySelector('#indexes-table tbody');
    tableBody.innerHTML = '';
  
    indexes.forEach(function(index) {
      let row = document.createElement('tr');
      row.innerHTML = `
        <td>${index.name}</td>
        <td>${index.column_name}</td>
        <td>${index.nullable ? 'Yes' : 'No'}</td>
        <td>${index.index_type}</td>
        <td>${index.non_unique}</td>
      `;
      tableBody.appendChild(row);
    });
  }

  function displaySequencesInfo(data) {
    if (data.num_sequence >= 0) {
        const div = document.getElementById("sequences_table_info");
        div.style.display = "block";
        
        

        // let tableName = document.getElementById("sequences-table-name");
        const tableName = div.querySelector('h2#sequences-table-name');
        tableName.textContent = data.name;

        // let sequence_input = document.getElementById("current_sequence");
        const sequenceGroup = div.querySelector("div#current_sequence_grp");
        const sequenceInput = div.querySelector("input#current_sequence");
        const sequenceUpdateButton = div.querySelector("button#update_sequence_button");
        
        sequenceGroup.style.display = 'none';
        sequenceGroup.style.display = 'none';

        console.log('tableName', tableName);
        if (data.num_sequence >= 0) {
            console.log('entrei aqui')
            sequenceInput.value = data.num_sequence || 0;
            sequenceGroup.style.display = '';
            sequenceUpdateButton.style.display = '';
        } else {
            console.log('entrei aqui 2')
            sequenceGroup.style.display = 'none';
            sequenceUpdateButton.style.display = 'none';
        }
    }

    socket.emit('handle_sequences', data.name, null);
  }


  function displayIndexInfo(data) {
    
    document.getElementById("indexes_table_info").style.display = "block";
    let tableName = document.getElementById("indexes-table-name");
    tableName.textContent = data.name;

    indexes = data.indexes;

    document.getElementById("indexes_table_info").style.display = "block";

    let tableBody = document.querySelector('#indexes-table-with-button tbody');
    tableBody.innerHTML = '';
  
    indexes.forEach(function(index) {
        let row = document.createElement('tr');
        let checkboxId = `index_checkbox_${index.name}`;
        row.innerHTML = `
          <td>${index.name}</td>
          <td><input type="checkbox" id="${checkboxId}" name="index_checkbox" ${index.excluded ? '' : 'checked'} ${index.name === 'PRIMARY' || index.non_unique === 0 ? 'disabled' : ''}></td>
        `;
        tableBody.appendChild(row);
      
   
        let checkbox = row.querySelector(`#${checkboxId}`);
        checkbox.addEventListener('click', function() {
          let isChecked = checkbox.checked;
          console.log(`Checkbox ${index.name} clicado!`);
          socket.emit('handle_specific_index', data.name, index.name, !isChecked);

        });
      });
    
  }


  function update_sequence_data(table, new_value){
        let tableName = document.getElementById("sequences-table-name");
       
        if(table != null && table == tableName.textContent){
            let sequence_input = document.getElementById("current_sequence");
            sequence_input.value = new_value;
        }
    }


  function changeFilter(dataTab, tabs) {

    for (let i = 0; i < tabs.length; i++) {
        let tab = tabs[i];
        const element = document.getElementById(tab.getAttribute('data-tab')+"_icon");
        element.style.filter = "invert(100%)";
    }
    const element = document.getElementById(dataTab+"_icon");
    element.style.filter =  "invert(100%) sepia(100%) saturate(5500%) hue-rotate(5deg)";
    
}



// Function to update progress bar
/* Função antiga da barra de progresso - comentada para usar Rich Progress
function updateProgressBar(bar, name, tuples, total) {
    const progress = bar.querySelector('.progress');
    const label = bar.querySelector('.label');

    // Calculate progress percentage
    const percentage = total > 0 ? (tuples / total) * 100 : 0;

    // Update progress bar width
    progress.style.width = percentage + '%';

    // Update data display
    label.querySelector('.name').textContent = name;
    label.querySelector('.data').textContent = tuples + ' / ' + total;
}
*/

// Função para renderizar o terminal Rich no frontend
function updateRichTerminal(data) {
    console.log("📡 updateRichTerminal called with action:", data.action);
    
    // Detectar se estamos na aba Partial (para migração parcial)
    const activeTab = document.querySelector('.tab-content.active');
    const isPartialTab = activeTab && activeTab.id === 'partial';
    
    // Usar terminal apropriado
    const terminalContainerId = isPartialTab ? 'partial_rich_terminal_container' : 'rich_terminal_container';
    const terminalContainer = document.getElementById(terminalContainerId);
    
    if (!terminalContainer) {
        console.error(`❌ Terminal container "${terminalContainerId}" not found!`);
        return;
    }
    
    console.log("✅ Terminal container found");
    console.log("📝 Raw output length:", data.output ? data.output.length : 0);
    
    // Converter códigos ANSI para HTML
    let terminalOutput = convertAnsiToHtml(data.output);
    
    // Limpar e processar o output para remover duplicatas
    if (terminalOutput) {
        // Dividir em linhas
        let lines = terminalOutput.split('\n');
        
        // Remover linhas vazias
        lines = lines.filter(line => line.trim().length > 0);
        
        // Pegar apenas as últimas linhas únicas (evitar duplicatas)
        const maxLines = 5; // Mostrar no máximo 5 linhas
        lines = lines.slice(-maxLines);
        
        terminalOutput = lines.join('\n');
    }
    
    console.log("📝 Processed output length:", terminalOutput.length);
    
    // SEMPRE substituir todo o conteúdo (para mostrar apenas uma barra que atualiza)
    terminalContainer.innerHTML = `<pre class="terminal-output">${terminalOutput}</pre>`;
    
    // Auto scroll para o final
    terminalContainer.scrollTop = terminalContainer.scrollHeight;
    
    console.log("✅ Terminal updated successfully");
}

// Função para converter códigos ANSI em HTML com cores
function convertAnsiToHtml(text) {
    if (!text) return '';
    
    // Mapa de cores ANSI
    const ansiColors = {
        '30': 'black',
        '31': 'red',
        '32': 'green',
        '33': 'yellow',
        '34': 'blue',
        '35': 'magenta',
        '36': 'cyan',
        '37': 'white',
        '90': 'bright-black',
        '91': 'bright-red',
        '92': 'bright-green',
        '93': 'bright-yellow',
        '94': 'bright-blue',
        '95': 'bright-magenta',
        '96': 'bright-cyan',
        '97': 'bright-white'
    };
    
    // Remover códigos de controle de cursor e limpeza (são usados pelo Rich para atualizar a mesma linha)
    // \x1b[?25l - esconder cursor
    // \x1b[?25h - mostrar cursor
    // \x1b[2K - limpar linha
    // \x1b[1G - mover cursor para início da linha
    // \x1b[nA - mover cursor n linhas para cima
    // \x1b[nB - mover cursor n linhas para baixo
    text = text.replace(/\x1b\[\?25[lh]/g, ''); // Controle de visibilidade do cursor
    text = text.replace(/\x1b\[[0-9]*[ABCDEFGJK]/g, ''); // Códigos de movimento e limpeza
    text = text.replace(/\x1b\[[0-9;]*[Hf]/g, ''); // Posicionamento do cursor
    
    // Escapar HTML
    text = text.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;');
    
    // Converter códigos ANSI de cor para spans com classes
    text = text.replace(/\x1b\[([0-9;]+)m/g, (match, codes) => {
        const codeList = codes.split(';');
        let classes = [];
        
        for (let code of codeList) {
            if (code === '0' || code === '') {
                return '</span>';
            } else if (code === '1') {
                classes.push('ansi-bold');
            } else if (ansiColors[code]) {
                classes.push('ansi-' + ansiColors[code]);
            }
        }
        
        if (classes.length > 0) {
            return '<span class="' + classes.join(' ') + '">';
        }
        return '';
    });
    
    // Remover qualquer código ANSI não processado
    text = text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');
    
    return text;
}

/* Função antiga do Rich Progress - mantida comentada caso necessário
function updateRichProgress(data) {
    const progressContainer = document.getElementById('rich_progress_container');
    
    if (!progressContainer) return;
    
    if (data.action === 'start') {
        progressContainer.innerHTML = `
            <div class="rich-progress-info">
                <h3>Iniciando migração de ${data.total_tables} tabelas (${data.total_tuples.toLocaleString()} tuplas)</h3>
            </div>
            <div id="overall_progress_bar" class="progress-bar">
                <div class="progress" style="width: 0%"></div>
                <div class="label">
                    <span class="name">Progresso Geral</span>
                    <span class="data">0 / ${data.total_tuples.toLocaleString()}</span>
                </div>
            </div>
            <div id="current_table_info"></div>
        `;
    } else if (data.action === 'table_start') {
        const tableInfo = document.getElementById('current_table_info');
        tableInfo.innerHTML = `
            <h4>Tabela ${data.table_index}/${data.total_tables}: ${data.table_name} (${data.table_tuples.toLocaleString()} tuplas)</h4>
            <div class="progress-bar">
                <div class="progress" id="current_table_progress" style="width: 0%"></div>
                <div class="label">
                    <span class="name">Progresso da Tabela</span>
                    <span class="data" id="current_table_data">0 / ${data.table_tuples.toLocaleString()}</span>
                </div>
            </div>
        `;
    } else if (data.action === 'file_progress') {
        // Progresso de escrita do arquivo CSV
        const percentage = (data.progress / data.total) * 100;
        document.getElementById('current_table_progress').style.width = percentage + '%';
        document.getElementById('current_table_data').textContent = `${data.progress.toLocaleString()} / ${data.total.toLocaleString()}`;
    } else if (data.action === 'migration_progress') {
        // Progresso de migração para PostgreSQL
        const tablePercentage = (data.progress / data.total) * 100;
        document.getElementById('current_table_progress').style.width = tablePercentage + '%';
        document.getElementById('current_table_data').textContent = `${data.progress.toLocaleString()} / ${data.total.toLocaleString()}`;
        
        const overallPercentage = (data.overall_progress / data.overall_total) * 100;
        const overallBar = document.querySelector('#overall_progress_bar .progress');
        const overallData = document.querySelector('#overall_progress_bar .data');
        if (overallBar) overallBar.style.width = overallPercentage + '%';
        if (overallData) overallData.textContent = `${data.overall_progress.toLocaleString()} / ${data.overall_total.toLocaleString()}`;
    } else if (data.action === 'table_complete') {
        const overallPercentage = (data.overall_progress / data.overall_total) * 100;
        const overallBar = document.querySelector('#overall_progress_bar .progress');
        const overallData = document.querySelector('#overall_progress_bar .data');
        if (overallBar) overallBar.style.width = overallPercentage + '%';
        if (overallData) overallData.textContent = `${data.overall_progress.toLocaleString()} / ${data.overall_total.toLocaleString()}`;
    } else if (data.action === 'complete') {
        progressContainer.innerHTML = `
            <div class="rich-progress-info success">
                <h3>✅ Migração concluída!</h3>
                <p>${data.total_tables} tabelas migradas (${data.total_tuples.toLocaleString()} tuplas)</p>
            </div>
        `;
    }
}
*/

// Função de debug para testar logs na aba ativa
function testLogInCurrentTab() {
    const activeTab = document.querySelector('.tab-content.active');
    const logContainer = getActiveLogContainer();
    
    console.log("=== DEBUG LOG TEST ===");
    console.log("Aba ativa:", activeTab ? activeTab.id : "Nenhuma");
    console.log("Container de log da aba:", logContainer ? 'Encontrado' : "Não encontrado");
    
    if (logContainer) {
        appendLogLine(logContainer, "INFO", "✅ Teste de log na aba " + (activeTab ? activeTab.id : "desconhecida") + ": " + new Date().toLocaleTimeString());
        console.log("✅ Log adicionado com sucesso na aba ativa!");
    } else {
        console.error("❌ Container de log não encontrado na aba ativa!");
    }
    console.log("=====================");
}

// Função para testar logs em todas as abas
function testAllTabs() {
    const tabs = document.querySelectorAll('.navbar-link');
    console.log("=== TESTANDO TODAS AS ABAS ===");
    
    tabs.forEach(tab => {
        const tabId = tab.getAttribute('data-tab');
        console.log(`\nTestando aba: ${tabId}`);
        
        // Simular clique na aba
        tab.click();
        
        setTimeout(() => {
            testLogInCurrentTab();
        }, 100);
    });
}

// Expor funções globalmente para teste via console do navegador
window.testLogInCurrentTab = testLogInCurrentTab;
window.testAllTabs = testAllTabs;


// ============================================================================
// PARTIAL MIGRATION FUNCTIONS
// ============================================================================

/**
 * Carrega lista de tabelas para o dropdown da aba Partial
 */
function loadTablesForPartial() {
    console.log("Loading tables for partial migration...");
    socket.emit('get_table_names_only');
}

/**
 * Handler para quando tabela é selecionada - carrega colunas temporais
 */
function onPartialTableSelect() {
    const tableSelect = document.getElementById('partial_table_select');
    const columnSelect = document.getElementById('partial_column_select');
    const tableName = tableSelect.value;
    
    // Limpar dropdown de colunas
    columnSelect.innerHTML = '<option value="">-- Select time column --</option>';
    
    if (!tableName) {
        return;
    }
    
    console.log(`Loading temporal columns for table: ${tableName}`);
    socket.emit('get_table_columns_by_name', tableName);
}

/**
 * Valida formulário de migração parcial
 */
function validatePartialForm() {
    const table = document.getElementById('partial_table_select').value;
    const column = document.getElementById('partial_column_select').value;
    const startDate = document.getElementById('partial_start_date').value;
    const endDate = document.getElementById('partial_end_date').value;
    
    if (!table) {
        alert('Please select a table');
        return false;
    }
    
    if (!column) {
        alert('Please select a time column');
        return false;
    }
    
    if (!startDate || !endDate) {
        alert('Please enter both start and end dates');
        return false;
    }
    
    // Validar que start_date <= end_date
    if (new Date(startDate) > new Date(endDate)) {
        alert('Start date must be before or equal to end date');
        return false;
    }
    
    return true;
}

/**
 * Botão: Executar migração parcial
 */
function BUTTON_migrate_partial() {
    if (!validatePartialForm()) {
        return;
    }
    
    const table = document.getElementById('partial_table_select').value;
    const column = document.getElementById('partial_column_select').value;
    const startDateRaw = document.getElementById('partial_start_date').value;
    const endDateRaw = document.getElementById('partial_end_date').value;
    
    // Adicionar horários automaticamente
    const startDate = startDateRaw + ' 00:00:00';
    const endDate = endDateRaw + ' 23:59:59';
    
    const mysqlBatch = parseInt(document.getElementById('partial_mysql_batch').value) || 5000;
    const postgresBulk = parseInt(document.getElementById('partial_postgres_bulk').value) || 5000;
    const strategy = document.querySelector('input[name="partial_strategy"]:checked').value;
    
    // Limpar terminal
    const terminal = document.querySelector('#partial_rich_terminal_container .terminal-output');
    if (terminal) {
        terminal.textContent = 'Starting partial migration...\n';
    }
    
    console.log('Starting partial migration:', {
        table, column, startDate, endDate, mysqlBatch, postgresBulk, strategy
    });
    
    socket.emit('migrate_partial_table', {
        table_name: table,
        filter_column: column,
        start_date: startDate,
        end_date: endDate,
        mysql_batch_size: mysqlBatch,
        postgres_bulk_size: postgresBulk,
        strategy: strategy
    });
}

/**
 * Botão: Reset progresso de migração parcial
 */
function BUTTON_reset_partial_progress() {
    const table = document.getElementById('partial_table_select').value;
    
    if (!table) {
        alert('Please select a table first');
        return;
    }
    
    if (!confirm(`Are you sure you want to reset progress for table "${table}"? This will clear any in-progress migration data.`)) {
        return;
    }
    
    console.log(`Resetting partial progress for table: ${table}`);
    socket.emit('reset_partial_progress', {
        table_name: table
    });
}

/**
 * Atualiza terminal da aba Partial com output rico
 */
function updatePartialRichTerminal(data) {
    const terminal = document.querySelector('#partial_rich_terminal_container .terminal-output');
    if (!terminal) return;
    
    if (data.action === 'start') {
        terminal.textContent = data.output || 'Starting...\n';
    } else if (data.action === 'append') {
        terminal.textContent += data.output || '';
    } else if (data.output) {
        terminal.textContent += data.output;
    }
    
    // Auto-scroll para o final
    terminal.scrollTop = terminal.scrollHeight;
}

// ============================================================================
// SOCKET HANDLERS FOR PARTIAL MIGRATION
// ============================================================================

socket.on('partial_table_names', (data) => {
    console.log('Received table names:', data);
    
    if (data.success && data.tables) {
        const tableSelect = document.getElementById('partial_table_select');
        
        // Limpar e popular dropdown
        tableSelect.innerHTML = '<option value="">-- Select table --</option>';
        data.tables.forEach(tableName => {
            const option = document.createElement('option');
            option.value = tableName;
            option.textContent = tableName;
            tableSelect.appendChild(option);
        });
        
        console.log(`Loaded ${data.tables.length} tables`);
    } else {
        console.error('Failed to load table names:', data.error);
        alert('Failed to load tables: ' + (data.error || 'Unknown error'));
    }
});

socket.on('partial_table_columns', (data) => {
    console.log('Received table columns:', data);
    
    if (data.success && data.columns) {
        const columnSelect = document.getElementById('partial_column_select');
        
        // Limpar e popular dropdown
        columnSelect.innerHTML = '<option value="">-- Select time column --</option>';
        data.columns.forEach(col => {
            const option = document.createElement('option');
            option.value = col.name;
            option.textContent = `${col.name} (${col.type})`;
            columnSelect.appendChild(option);
        });
        
        console.log(`Loaded ${data.columns.length} temporal columns for table ${data.table}`);
        
        if (data.columns.length === 0) {
            alert(`No temporal columns (DATE, DATETIME, TIMESTAMP) found in table "${data.table}"`);
        }
    } else {
        console.error('Failed to load columns:', data.error);
        alert('Failed to load columns: ' + (data.error || 'Unknown error'));
    }
});

socket.on('partial_migration_result', (data) => {
    console.log('Partial migration result:', data);
    
    const terminal = document.querySelector('#partial_rich_terminal_container .terminal-output');
    
    if (data.success) {
        const message = `\n✅ Migration completed successfully!\n` +
                       `   Table: ${data.table}\n` +
                       `   Rows migrated: ${data.rows_migrated.toLocaleString()}\n` +
                       `   Batches: ${data.batches}\n`;
        if (terminal) terminal.textContent += message;
        alert(`Migration completed! ${data.rows_migrated.toLocaleString()} rows migrated.`);
    } else {
        const message = `\n❌ Migration failed: ${data.error}\n`;
        if (terminal) terminal.textContent += message;
        alert('Migration failed: ' + data.error);
    }
});

socket.on('partial_reset_result', (data) => {
    console.log('Reset progress result:', data);
    
    if (data.success) {
        alert(`Progress reset for table "${data.table}". Removed ${data.removed} entries.`);
    } else {
        alert('Failed to reset progress: ' + data.error);
    }
});

