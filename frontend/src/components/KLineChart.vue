<template>
  <div ref="chartRef" style="width:100%;height:500px"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ kline: { type: Array, default: () => [] } })
const chartRef = ref(null)
let chart = null

function render() {
  if (!chartRef.value || !props.kline.length) return
  if (!chart) chart = echarts.init(chartRef.value)
  // Date axis
  const dates = props.kline.map(r => r.date)
  const ohlc = props.kline.map(r => [+r.open, +r.close, +r.low, +r.high])
  const vol = props.kline.map(r => +r.volume)
  const ma5 = props.kline.map(r => +r.ma5)
  const ma20 = props.kline.map(r => +r.ma20)
  const macdD = props.kline.map(r => +r.macd_dif)
  const macdH = props.kline.map(r => +r.macd_hist)

  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线','MA5','MA20','成交量','MACD'], top: 0 },
    grid: [{ left:'8%',right:'3%',top:'8%',height:'55%' },{ left:'8%',right:'3%',top:'72%',height:'18%' }],
    xAxis: [{ type:'category',data:dates,gridIndex:0,axisLabel:{rotate:30,fontSize:10} },
            { type:'category',data:dates,gridIndex:1 }],
    yAxis: [{ scale:true,gridIndex:0 },{ scale:true,gridIndex:1,position:'right' }],
    series: [
      { type:'candlestick',data:ohlc,xAxisIndex:0,yAxisIndex:0,itemStyle:{color:'#ef5350',color0:'#26a69a',borderColor:'#ef5350',borderColor0:'#26a69a'} },
      { type:'line',data:ma5,smooth:true,lineStyle:{color:'#fdb813',width:1},xAxisIndex:0,yAxisIndex:0,showSymbol:false },
      { type:'line',data:ma20,smooth:true,lineStyle:{color:'#f06292',width:1},xAxisIndex:0,yAxisIndex:0,showSymbol:false },
      { type:'bar',data:vol,xAxisIndex:1,yAxisIndex:1,itemStyle:{color:function(p){return props.kline[p.dataIndex]?.pct_chg>0?'#26a69a':'#ef5350'}} },
      { type:'bar',data:macdH,xAxisIndex:1,yAxisIndex:1,itemStyle:{color:function(p){return p.value>=0?'#ef5350':'#26a69a'}} },
    ]
  })
}

watch(()=>props.kline, ()=>{nextTick(render)})
onMounted(()=>{render(); window.addEventListener('resize',()=>chart?.resize())})
onUnmounted(()=>{chart?.dispose()})
defineExpose({ getChart:()=>chart })
</script>