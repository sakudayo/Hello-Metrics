google.load('visualization', '1', {packages:['table', 'corechart']});

// Cookie helpers -------------------------------------------------------------
var setCookie = function(name, value, exp_y, exp_m, exp_d, path, domain, secure) {
    var cookie_string = name + "=" + escape (value);

    if (exp_y) { 
        var expires = new Date (exp_y, exp_m, exp_d);
        cookie_string += "; expires=" + expires.toGMTString();
    }
    if (path) {
        cookie_string += "; path=" + escape (path);
    }

    if (domain) {
        cookie_string += "; domain=" + escape (domain);
    }
      
    if (secure) {
        cookie_string += "; secure";
    }
        
    document.cookie = cookie_string;
}

var getCookie = function(cookie_name) {
    var results = document.cookie.match ('(^|;) ?' + cookie_name + '=([^;]*)(;|$)');

    if (results)
        return (unescape(results[2]));
    else
        return null;
} 

// ----------------------------------------------------------------------------

// checking if token is present
if (/access_token=([^&]+)/.exec(document.location.hash)) {
    setCookie('token', /access_token=([^&]+)/.exec(document.location.hash)[1], '', '', '', '/', '', '');
}
else if (!getCookie('token')) {
    window.location = 'https://oauth.yandex.ru/authorize?response_type=token&client_id=7f1a2fa7412547edb032ba10df396990';
}

// ----------------------------------------------------------------------------
var add_datepicker = function(objects) {
    for (var i = 0; i < objects.length; i++) {
        objects[i].datepicker({ changeMonth: true,
                            changeYear: true,
                            dateFormat: 'yy-mm-dd',
                            showOtherMonths: true,
                            selectOtherMonths: true
                        });
    }
}

var drawChart = function(chart_data, name1, name2) {
    // line chart
    var data = new google.visualization.DataTable();
    var graph_data = chart_data["dates"];
       
    data.addColumn('string', 'День');
    data.addColumn('number', name2);
    data.addColumn('number', name1);
       
    rows = []
    for (var i = graph_data.length - 1; i >= 0; i--) {
        rows.push([graph_data[i]["date"], graph_data[i]["former_visits"], graph_data[i]["visits"]]);
    }
    data.addRows(rows);

    var chart = new google.visualization.LineChart(document.getElementById('graph'));
    chart.draw(data, {width: 1000, 
                      height: 450, 
                      title: 'Сравнение посещаемости', 
                      pointSize: 12, 
                      colors:['green','red'], 
                      lineWidth: 6, 
                      legend: "top", 
                      vAxis: {title: 'Визиты', titleTextStyle: {color: '#FF0000'}}
                     }
               );
    
    // bar chart
    data = new google.visualization.DataTable();
    data.addColumn('string', 'Дата');
    data.addColumn('number', 'Отклонение');
    data.addRows(graph_data.length);
    rows = []
    var mean = chart_data["mean"]
    for (var i = graph_data.length - 1; i >= 0; i--) {
        data.setValue(graph_data.length - 1 - i, 0, graph_data[i]["date"]);
        data.setValue(graph_data.length - 1 - i, 1, Math.abs(graph_data[i]["visits"] - mean));
    }

    var chart = new google.visualization.ColumnChart(document.getElementById('deviation'));
    chart.draw(data, {width: 800, 
                      height: 100, 
                      title: 'Отклонение от среднего', 
                      vAxis: {title: 'Визиты', titleTextStyle: {color: 'red'}}, 
                      legend: "none"
                     }
               );
}

var drawTable = function(table_data) {
    // pages table
    var data = new google.visualization.DataTable();
    data.addColumn('string', 'Адрес страницы');
    data.addColumn('number', 'Просмотров');
    data.addColumn('number', 'Было просмотров');
    data.addColumn('number', 'Входов');
    data.addColumn('number', 'Выходов');
    data.addColumn('string', 'Δ Места');
    data.addRows(table_data.length);
        
    for (var i = 0; i < table_data.length; i++) {
        data.setCell(i, 0, table_data[i]["url"].replace(/http:\/\//, ""));
        data.setCell(i, 1, table_data[i]["page_views"]);
        data.setCell(i, 2, table_data[i]["former_page_views"]);
        data.setCell(i, 3, table_data[i]["entrances"]);
        data.setCell(i, 4, table_data[i]["exits"]);
        var delta = table_data[i]["delta_place"];
        var st = 'font-weight:bold;color:';
        if (delta > 0) {
            st += 'green;';
        }
        else if (delta < 0) {
            st += 'red;';
        }
        else {
            st += '#C9960C;';
        }
        data.setCell(i, 5, delta);
        data.setProperty(i, 5, 'style', st); // strangely doesn't work if used in setCell
     }
        
     var table = new google.visualization.Table(document.getElementById('pages'));
     table.draw(data, {showRowNumber: true, 
                       sortColumn: 1, 
                       sortAscending: false, 
                       allowHtml: true 
                      }
                );
}
      

// ----------------------------------------------------------------------------
$(function() {
    // calendar
    add_datepicker([$("#date_1"), $("#date_2")]);
              
    // getting counters info
    $.ajax({
        url: "/counters",
        type: "POST",
        data: "token=" + getCookie('token'),
        success: function(result){
            var data = $.parseJSON(result);
            $("#counter").empty();
            result = '';
            for (var i = 0; i < data.length; i++) {
                result += '<option value="' + data[i]["id"] +'">' + data[i]["site"] + '</option>';
            }                
            $("#counter").append(result);
        }
    });
                 
    // making button glossy
    $("#submit_button").button();
    
    $("#submit_button").click( function() {

            $("#graph").html('<img src="/static/loading.gif" alt="Please wait" class="wait_image" />');
            $("#deviation").html('<img src="/static/loading.gif" alt="Please wait" class="wait_image" />');
            $("#pages").html('<img src="/static/loading.gif" alt="Please wait" class="wait_image" />');
            
            $.ajax({
                url: "/dates",
                type: "POST",
                data: "counter=" + $("select").val() + "&date_1=" + $("#date_1").val() + "&date_2=" + $("#date_2").val() + "&token=" + getCookie('token'),
                success: function(result){
                    try {
                        var data = $.parseJSON(result);
                        if (google.visualization.DataTable) {
                            drawChart(data, "Позже", "Раньше");
                        }
                        else {
                            google.setOnLoadCallback(function() { drawChart(data, "Позже", "Раньше"); });
                        }
                    } catch(e) { 
                        if (e instanceof SyntaxError) {
                            $("#graph").html(result);
                            $("#deviation").empty();
                        }
                        else {
                            $("#graph").html('<p>Что-то пошло не так :(</p>');
                            $("#deviation").html('<p>Что-то пошло не так :(</p>');
                        }
                    }
                },
                error: function() {
                    $("#graph").html('<p>Что-то пошло не так :(</p>');
                    $("#deviation").html('<p>Что-то пошло не так :(</p>');
                }
              });
            
            $.ajax({
              url: "/pages",
              type: "POST",
              data: "counter=" + $("select").val() + "&date_1=" + $("#date_1").val() + "&date_2=" + $("#date_2").val() + "&token=" + getCookie('token'),
              success: function(result){
                    try {
                        var data = $.parseJSON(result);
                        if (google.visualization.Table) {
                            drawTable(data);
                        }
                        else {
                            google.setOnLoadCallback(function() { drawTable(data); });
                        }
                    } catch(e) { 
                        if (e instanceof SyntaxError) {
                            $("#graph").html(result);
                            $("#deviation").empty();
                        }
                        else {
                            $("#graph").html('<p>Что-то пошло не так :(</p>');
                            $("#deviation").html('<p>Что-то пошло не так :(</p>');
                        }
                    }
              },
              error: function() {
                  $("#pages").html('<p>Что-то пошло не так :(</p>');
              }
            });
        });
}); 