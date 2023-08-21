// 從Flask傳遞的數據
var data = {{ data|safe }};
var trade_data = {{ trade_data|safe }};
console.log(data)
console.log(trade_data)
// 解析JSON字符串為JavaScript對象
// data = JSON.parse(data);
// trade_data = JSON.parse(trade_data);

// 使用Plotly.js繪製蠟燭圖和移動平均線
var trace1 = {
    x: data.map(d => d.date),
    open: data.map(d => d.open),
    high: data.map(d => d.high),
    low: data.map(d => d.low),
    close: data.map(d => d.close),
    type: 'candlestick',
    name: '股票價格'
};

var trace2 = {
    x: data.map(d => d.date),
    y: data.map(d => d.MA5),
    type: 'scatter',
    name: 'MA5'
};

var trace3 = {
    x: data.map(d => d.date),
    y: data.map(d => d.MA20),
    type: 'scatter',
    name: 'MA20'
};

// 繪製買賣點位
var trace4 = {
    x: trade_data.filter(d => d.type === 'buy').map(d => d.date),
    y: trade_data.filter(d => d.type === 'buy').map(d => d.price),
    text: trade_data.filter(d => d.type === 'sell').map(d => d.volume), // 添加成交量信息
    mode: 'markers',
    type: 'scatter',
    name: '買點',
    marker: {
        size: 10,
        color: 'green'
    },
    hovertemplate: '日期:<b>%{x}</b><br><b>%{y:$.2f}</b><br>%{text}<extra></extra>',

};

var trace5 = {
    x: trade_data.filter(d => d.type === 'sell').map(d => d.date),
    y: trade_data.filter(d => d.type === 'sell').map(d => d.price),
    text: trade_data.filter(d => d.type === 'sell').map(d => d.volume), // 添加成交量信息
    mode: 'markers',
    type: 'scatter',
    name: '賣點',
    marker: {
        size: 10,
        color: 'red'
    },
    hovertemplate: '日期:<b>%{x}</b><br><b>%{y:$.2f}</b><br>%{text}<extra></extra>',
};

var layout = {
    hovermode:'closest',

    title: '股票價格和移動平均線',
    xaxis: {
        title: '日期',
        fixedrange: true,
        rangeslider: {visible: false}
    },
    yaxis: {
        title: '價格' 
    },
    // 調整圖表的寬度和高度
    width: 800,
    height: 600,
    // 隱藏sliders
    sliders: [{
        visible: false
    }]
};
Plotly.newPlot('plot', [trace1, trace2, trace3, trace4, trace5], layout);
var plotDiv = document.getElementById('plot');
plotDiv.on('plotly_click', function(data){
    var point = data.points[0];
    if (point.data.name === '買點' || point.data.name === '賣點') {
        document.getElementById("date").innerHTML = point.x;
        document.getElementById("action").innerHTML = point.data.name ;
        document.getElementById("price").innerHTML = point.y;
        document.getElementById("volume").innerHTML = point.text;
        fetch('/check_point', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                date: point.x,
                price: point.y,
                type: point.data.name === '買點' ? 'buy' : 'sell',
                option: "{{option}}",
                rule: "{{rule}}",
            })
        })
        .then(response => response.json())
        .then(data => {
            // 從後端獲取響應並在前端顯示
            console.log(data);
            console.log(data['違反'])
            var violateElement = document.getElementById('violate');
            while (violateElement.nextSibling) {
                violateElement.nextSibling.remove();
            }

            data['違反'].forEach(function(item) {
                if(item != 'nan'){
                var newItem = document.createElement('b');
                newItem.textContent = item;
                violateElement.parentNode.insertBefore(newItem, violateElement.nextSibling);
                }
            });
            var followElement = document.getElementById('follow');
            while (followElement.nextSibling) {
                followElement.nextSibling.remove();
            }
            data['遵守'].forEach(function(item) {
                if(item != 'nan'){
                var newItem = document.createElement('b');
                newItem.textContent = item;
                followElement.parentNode.insertBefore(newItem, followElement.nextSibling);
                }
            });
            // stay = String(data['待決定']).split("-");
            stay = data['待決定']
            let form = document.querySelector('form[action="/update_custom"]');
            let submit = document.createElement('input');
            submit.type = 'submit';
            while (form.firstChild) {
                form.removeChild(form.firstChild);
            }
            // 創建第一個隱藏輸入字段
            var input1 = document.createElement('input');
            input1.type = 'hidden';
            input1.id = 'hiddenDate';
            input1.name = 'date';
            input1.value = document.getElementById("date").innerHTML;
            form.appendChild(input1); // 將輸入字段添加到表單中

            // 創建第二個隱藏輸入字段
            var input2 = document.createElement('input');
            input2.type = 'hidden';
            input2.id = 'hiddenPrice';
            input2.name = 'price';
            input2.value = document.getElementById("price").innerHTML;

            form.appendChild(input2); // 將輸入字段添加到表單中

            // 創建第三個隱藏輸入字段
            var input3 = document.createElement('input');
            input3.type = 'hidden';
            input3.id = 'hiddenAction';
            input3.name = 'action';
            input3.value = document.getElementById("action").innerHTML;
            form.appendChild(input3); // 將輸入字段添加到表單中

            for (let custom of stay) {
                if(custom != 'nan'){
                let label = document.createElement('label');
                label.setAttribute('for', custom);
                label.textContent = custom + ':';
                form.appendChild(label);

                let select = document.createElement('select');
                select.id = custom;
                select.name = custom;
                let option1 = document.createElement('option');
                option1.value = '遵守';
                option1.textContent = '遵守';
                select.appendChild(option1);

                let option2 = document.createElement('option');
                option2.value = '違反';
                option2.textContent = '違反';
                select.appendChild(option2);
                form.appendChild(select);

                form.appendChild(document.createElement('br'));
                }


            }
            form.appendChild(submit);

        });

    }
});
window.onload = function() {
    var profit = document.getElementById("data2").innerHTML;
    document.getElementById("profit").value = profit;
    var ratio = document.getElementById("data3").innerHTML;
    document.getElementById("ratio").value = ratio;
    var number = document.getElementById("data4").innerHTML;
    document.getElementById("number").value = number;
    var duration = document.getElementById("data5").innerHTML;
    document.getElementById("duration").value = duration;

}
