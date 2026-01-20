import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import plotly.io as pio

# Configuración de la página
st.set_page_config(page_title="Control de Tubería", layout="wide")

# --- 📱 MEJORA MOBILE: INYECCIÓN DE CSS ---
st.markdown("""
    <style>
    /* Reducir el padding del contenedor principal para ganar espacio en móvil */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    /* Ajustar tamaño de fuentes en métricas */
    [data-testid="stMetricValue"] {
        font-size: 1.2rem;
    }
    /* Hacer que los tabs y expanders ocupen el 100% real */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard de Control de Tubería - CPP")
st.markdown("---")

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
SHEET_ID = "1UIEUpEm0id9IHvNkIvleoNGFT2FHGAKE"
SHEET_GID = "1124944326"
GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={SHEET_GID}"

# --- 📱 MEJORA MOBILE: CONFIGURACIÓN PLOTLY ---
config_mobile = {
    'displayModeBar': False, 
    'displaylogo': False,
    'scrollZoom': False
}

# FUNCIÓN HELPER PARA ADAPTAR GRÁFICOS A MÓVIL
def adaptar_grafico_mobile(fig):
    """Mueve la leyenda arriba y reduce márgenes para ganar espacio horizontal"""
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    return fig

# BOTÓN PARA ACTUALIZAR DATOS MANUALMENTE
if st.button('🔄 Actualizar Datos Ahora', use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Cargar datos
@st.cache_data(ttl=60) 
def cargar_datos(archivo_path):
    # Leer sin encabezado para manejar manualmente
    df = pd.read_excel(archivo_path, header=None)
    encabezados = df.iloc[1].tolist()
    df_datos = df.iloc[2:].reset_index(drop=True)
    df_datos.columns = encabezados

    fecha_cols = []
    fecha_cols_display = []
    for i, col in enumerate(encabezados[10:], start=10):
        if pd.notna(col):
            if isinstance(col, (pd.Timestamp, datetime)):
                fecha_str = col.strftime('%d/%m/%Y')
                fecha_cols.append(fecha_str)
                fecha_display = col.strftime('%d/%m')
                fecha_cols_display.append(fecha_display)
            else:
                try:
                    fecha_dt = pd.to_datetime(col)
                    fecha_str = fecha_dt.strftime('%d/%m/%Y')
                    fecha_cols.append(fecha_str)
                    fecha_display = fecha_dt.strftime('%d/%m')
                    fecha_cols_display.append(fecha_display)
                except:
                    fecha_cols.append(str(col))
                    fecha_cols_display.append(str(col))

    columnas_nuevas = encabezados[:10] + fecha_cols
    if len(encabezados) > len(columnas_nuevas):
        columnas_nuevas += [f'Extra_{i}' for i in range(len(columnas_nuevas), len(encabezados))]

    df_datos.columns = columnas_nuevas[:len(df_datos.columns)]

    for fecha_col in fecha_cols:
        if fecha_col in df_datos.columns:
            df_datos[fecha_col] = pd.to_numeric(df_datos[fecha_col], errors='coerce')
            df_datos[fecha_col] = df_datos[fecha_col].fillna(0)
            df_datos[fecha_col] = df_datos[fecha_col].clip(lower=0)

    return df_datos, fecha_cols, fecha_cols_display

# ✅ FUNCIÓN PARA EXPORTAR GRÁFICOS
def exportar_grafico_png(figura, ancho=1200, alto=600):
    try:
        buffer = BytesIO()
        figura.write_image(
            buffer,
            format='png',
            width=ancho,
            height=alto,
            scale=2,
            engine='kaleido'
        )
        buffer.seek(0)
        return buffer
    except Exception as e:
        return None

def generar_pdf_reporte(df_filtrado, fecha_cols, fecha_cols_display, tipo_seleccionado, fig_linea, fig_barras, fig_pie, fig_heatmap, fig_acum):
    """Genera un PDF completo con todos los gráficos y tablas"""
    
    pdf_buffer = BytesIO()
    
    doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4),
                           rightMargin=0.5*inch, leftMargin=0.5*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1f77b4'), spaceAfter=12, alignment=TA_CENTER, fontName='Helvetica-Bold')
    encabezado_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#333333'), spaceAfter=8, spaceBefore=8, fontName='Helvetica-Bold')
    
    elements.append(Paragraph("📊 Control de montaje de tuberia - CAD proyectos Perú S.A.C.", titulo_style))
    elements.append(Paragraph(f"Reporte generado: {datetime.now().strftime('%d/%m/%Y a las %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    tipos_texto = ", ".join(tipo_seleccionado) if tipo_seleccionado else "Todas"
    elements.append(Paragraph(f"Tipos de Línea: {tipos_texto}", styles['Normal']))
    elements.append(Spacer(1, 0.1*inch))
    
    # --- 🔄 MODIFICACIÓN PDF: CÁLCULO DE NUEVAS MÉTRICAS ---
    # 1. Contar tipos de línea únicos
    num_tipos_linea = df_filtrado['LINEA'].nunique()
    
    # 2. Avance total (para añadir 'ml')
    avance_total = df_filtrado[fecha_cols].clip(lower=0).sum().sum()
    
    # 3. Longitud Total
    longitud_total = pd.to_numeric(df_filtrado['Longitud Total (m)'], errors='coerce').sum()
    
    # 4. Cálculo de % Global
    if longitud_total > 0:
        porcentaje_global = (avance_total / longitud_total) * 100
    else:
        porcentaje_global = 0
    
    metricas_data = [
        ['Cant. Tipos de Línea', str(num_tipos_linea)],          # Modificado
        ['Avance Total', f"{int(avance_total):,} ml"],           # Modificado (ml)
        ['Longitud Total (m)', f"{longitud_total:,.1f}"],
        ['% Avance Global', f"{porcentaje_global:.1f}%"]         # Modificado (% Global)
    ]
    
    table_metricas = Table(metricas_data, colWidths=[3*inch, 3*inch])
    table_metricas.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E8F4F8')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    elements.append(table_metricas)
    elements.append(Spacer(1, 0.2*inch))
    elements.append(PageBreak())
    
    # ... (Resto de la generación de gráficos PDF igual que antes) ...
    if fig_linea is not None:
        try:
            fig_linea.update_layout(paper_bgcolor='white', plot_bgcolor='rgba(240,240,240,0.5)', font=dict(family="Arial", size=11, color='black'), margin=dict(l=50, r=50, t=50, b=50), legend=dict(orientation="v", x=1.02))
            img_linea = exportar_grafico_png(fig_linea, ancho=1400, alto=500)
            if img_linea:
                elements.append(Paragraph("Avance Diario Total", encabezado_style))
                img_obj = Image(img_linea, width=7.5*inch, height=3*inch)
                elements.append(img_obj)
                elements.append(Spacer(1, 0.2*inch))
        except: pass
    
    if fig_barras is not None:
        try:
            fig_barras.update_layout(paper_bgcolor='white', plot_bgcolor='rgba(240,240,240,0.5)', font=dict(family="Arial", size=11, color='black'), margin=dict(l=50, r=50, t=50, b=50))
            img_barras = exportar_grafico_png(fig_barras, ancho=1400, alto=500)
            if img_barras:
                elements.append(Paragraph("Avance por Tipo de Línea", encabezado_style))
                img_obj = Image(img_barras, width=7.5*inch, height=3*inch)
                elements.append(img_obj)
                elements.append(Spacer(1, 0.2*inch))
        except: pass
    
    elements.append(PageBreak())
    
    if fig_pie is not None:
        try:
            fig_pie.update_layout(paper_bgcolor='white', font=dict(family="Arial", size=11, color='black'), margin=dict(l=50, r=50, t=50, b=50))
            img_pie = exportar_grafico_png(fig_pie, ancho=1200, alto=600)
            if img_pie:
                elements.append(Paragraph("Distribución por Servicio", encabezado_style))
                img_obj = Image(img_pie, width=6.5*inch, height=3.25*inch)
                elements.append(img_obj)
                elements.append(Spacer(1, 0.2*inch))
        except: pass
    
    elements.append(Paragraph("Tabla de Porcentajes de Avance", encabezado_style))
    avance_por_linea = []
    for linea in df_filtrado['LINEA'].unique():
        if pd.notna(linea):
            df_linea = df_filtrado[df_filtrado['LINEA'] == linea]
            avance_limpio = df_linea[fecha_cols].clip(lower=0).sum().sum()
            longitud_total_linea = pd.to_numeric(df_linea['Longitud Total (m)'], errors='coerce').sum()
            porcentaje_avance = (avance_limpio / longitud_total_linea) * 100 if longitud_total_linea > 0 else 0
            if avance_limpio > 0 or longitud_total_linea > 0:
                avance_por_linea.append({'Tipo de Línea': linea, 'Avance': avance_limpio, 'Longitud Total': longitud_total_linea, 'Porcentaje': porcentaje_avance})
    
    df_por_linea = pd.DataFrame(avance_por_linea)
    if not df_por_linea.empty:
        df_por_linea = df_por_linea.sort_values('Avance', ascending=False)
        tabla_data = [['Tipo de Línea', 'Avance', 'Longitud (m)', '% Avance']]
        for _, row in df_por_linea.iterrows():
            tabla_data.append([row['Tipo de Línea'][:30], f"{int(row['Avance']):,}", f"{row['Longitud Total']:.1f}", f"{row['Porcentaje']:.1f}%"])
        total_avance = df_por_linea['Avance'].sum()
        total_longitud = df_por_linea['Longitud Total'].sum()
        total_porcentaje = (total_avance / total_longitud * 100) if total_longitud > 0 else 0
        tabla_data.append(['📊 TOTAL', f"{int(total_avance):,}", f"{total_longitud:.1f}", f"{total_porcentaje:.1f}%"])
        table_porcentajes = Table(tabla_data, colWidths=[2.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
        table_porcentajes.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFD700')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F0F0F0')])
        ]))
        elements.append(table_porcentajes)
        elements.append(Spacer(1, 0.2*inch))
    
    elements.append(PageBreak())
    if fig_heatmap is not None:
        try:
            fig_heatmap.update_layout(paper_bgcolor='white', font=dict(family="Arial", size=11, color='black'), margin=dict(l=50, r=50, t=50, b=50))
            img_heatmap = exportar_grafico_png(fig_heatmap, ancho=1400, alto=600)
            if img_heatmap:
                elements.append(Paragraph("Mapa de Calor - Intensidad de Avance", encabezado_style))
                img_obj = Image(img_heatmap, width=7.5*inch, height=3*inch)
                elements.append(img_obj)
                elements.append(Spacer(1, 0.2*inch))
        except: pass
    
    if fig_acum is not None:
        try:
            fig_acum.update_layout(paper_bgcolor='white', plot_bgcolor='rgba(240,240,240,0.5)', font=dict(family="Arial", size=11, color='black'), margin=dict(l=50, r=50, t=50, b=50))
            img_acum = exportar_grafico_png(fig_acum, ancho=1400, alto=500)
            if img_acum:
                elements.append(Paragraph("Progreso Acumulado", encabezado_style))
                img_obj = Image(img_acum, width=7.5*inch, height=3*inch)
                elements.append(img_obj)
                elements.append(Spacer(1, 0.2*inch))
        except: pass
    
    elements.append(PageBreak())
    elements.append(Paragraph("Detalle por Tipo de Línea y Día", encabezado_style))
    tabla_resumen = []
    for linea in df_filtrado['LINEA'].unique():
        if pd.notna(linea):
            df_linea = df_filtrado[df_filtrado['LINEA'] == linea]
            fila = {'Tipo de Línea': linea}
            total_linea = 0
            for i, fecha_col in enumerate(fecha_cols):
                valor = df_linea[fecha_col].clip(lower=0).sum()
                if valor > 0:
                    fecha_corta = fecha_cols_display[i] if i < len(fecha_cols_display) else fecha_col
                    fila[fecha_corta] = int(valor)
                    total_linea += valor
            if total_linea > 0:
                fila['Total'] = int(total_linea)
                tabla_resumen.append(fila)
    if tabla_resumen:
        df_tabla = pd.DataFrame(tabla_resumen)
        cols = [c for c in df_tabla.columns if c != 'Total']
        if 'Total' in df_tabla.columns: cols.append('Total')
        df_tabla = df_tabla[cols]
        cols_mostradas = [df_tabla.columns[0]] + list(df_tabla.columns[-7:])
        df_tabla_reducida = df_tabla[cols_mostradas] if len(df_tabla.columns) > 8 else df_tabla
        tabla_data = [list(df_tabla_reducida.columns)]
        for _, row in df_tabla_reducida.iterrows(): tabla_data.append([str(v) for v in row])
        col_widths = [2*inch] + [0.6*inch] * (len(tabla_data[0]) - 1)
        table_resumen = Table(tabla_data, colWidths=col_widths)
        table_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')])
        ]))
        elements.append(table_resumen)
        elements.append(Spacer(1, 0.2*inch))
    
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(f"Documento generado automáticamente el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}", styles['Normal']))
    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- SIDEBAR ---
st.sidebar.header("📁 Fuente de Datos")
st.sidebar.info(f"Conectado a Google Sheets")

archivo_subido = st.sidebar.file_uploader("O cargar archivo manual (opcional)", type=['xlsx', 'xls'])
if archivo_subido is not None:
    archivo_path = archivo_subido
    st.sidebar.success("Usando archivo subido manualmente")
else:
    archivo_path = GOOGLE_SHEET_URL

try:
    with st.spinner('Cargando datos desde Google Sheets...'):
        df, fecha_cols, fecha_cols_display = cargar_datos(archivo_path)
    origen = "Google Sheets" if archivo_subido is None else "Archivo Local"
    st.sidebar.success(f"✅ Datos cargados de {origen}: {len(df)} líneas")
except Exception as e:
    st.error(f"❌ Error al cargar los datos: {str(e)}")
    st.info("💡 Si usas Google Sheets, asegúrate de que el archivo sea público o accesible mediante enlace.")
    st.stop()

# Sidebar con filtros
st.sidebar.header("🔍 Filtros")
tipos_linea = df['LINEA'].dropna().unique()
tipo_seleccionado = st.sidebar.multiselect(
    "Tipo de Línea:",
    options=tipos_linea,
    default=list(tipos_linea)
)

if not tipo_seleccionado:
    st.warning("⚠️ Por favor, selecciona al menos un tipo de línea para visualizar.")
    st.stop()

# Filtrar datos
df_filtrado = df[df['LINEA'].isin(tipo_seleccionado)]

# --- 🔄 MODIFICACIÓN DASHBOARD: MÉTRICAS ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    # 1. Contar el tipo de líneas (únicas)
    num_tipos_linea = df_filtrado['LINEA'].nunique()
    st.metric("Cant. Tipos de Línea", num_tipos_linea)

with col2:
    # 2. Agregar unidad (ml)
    avance_total = df_filtrado[fecha_cols].clip(lower=0).sum().sum()
    st.metric("Avance Total", f"{int(avance_total):,} ml")

with col3:
    longitud_total = pd.to_numeric(df_filtrado['Longitud Total (m)'], errors='coerce').sum()
    st.metric("Longitud Total (m)", f"{longitud_total:,.1f}")

with col4:
    # 3. Cambiar Tipos de Servicio por % Avance Global
    if longitud_total > 0:
        pct_global = (avance_total / longitud_total) * 100
    else:
        pct_global = 0
    st.metric("% Avance Global", f"{pct_global:.1f}%")

st.markdown("---")

# Análisis por día
st.header("📈 Avance por Día")

avance_diario = []
for i, fecha_col in enumerate(fecha_cols):
    valor = df_filtrado[fecha_col].clip(lower=0).sum()
    fecha_display = fecha_cols_display[i] if i < len(fecha_cols_display) else fecha_col
    avance_diario.append({'Fecha': fecha_display, 'Fecha_Completa': fecha_col, 'Avance': valor})

df_avance = pd.DataFrame(avance_diario)
df_avance = df_avance[df_avance['Avance'] > 0]

fig_linea = None

if not df_avance.empty:
    fig_linea = px.line(df_avance, x='Fecha', y='Avance',
                       title='Avance Diario Total',
                       markers=True,
                       labels={'Avance': 'Cantidad', 'Fecha': 'Fecha (día/mes)'},
                       hover_data={'Fecha_Completa': True, 'Avance': True},
                       text='Avance')
    
    fig_linea.update_traces(
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8),
        textposition='top center',
        texttemplate='%{text:.0f}'
    )
    
    fig_linea.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_tickangle=-45,
        paper_bgcolor='white',
        plot_bgcolor='rgba(240,240,240,0.5)',
        font=dict(family="Arial", size=12, color='#333333')
    )
    
    fig_linea = adaptar_grafico_mobile(fig_linea)
    st.plotly_chart(fig_linea, use_container_width=True, config=config_mobile)
else:
    st.info("No hay datos de avance para mostrar en el gráfico temporal.")

# Análisis por tipo de servicio
st.markdown("---")
st.header("🔧 Avance por Tipo de Servicio")

col_left, col_right = st.columns(2)

fig_barras = None
fig_pie = None

with col_left:
    avance_por_linea = []
    for linea in df_filtrado['LINEA'].unique():
        if pd.notna(linea):
            df_linea = df_filtrado[df_filtrado['LINEA'] == linea]
            avance_limpio = df_linea[fecha_cols].clip(lower=0).sum().sum()
            longitud_total_linea = pd.to_numeric(df_linea['Longitud Total (m)'], errors='coerce').sum()
            
            if longitud_total_linea > 0:
                porcentaje_avance = (avance_limpio / longitud_total_linea) * 100
            else:
                porcentaje_avance = 0
            
            if avance_limpio > 0 or longitud_total_linea > 0:
                avance_por_linea.append({
                    'Tipo de Línea': linea,
                    'Avance': avance_limpio,
                    'Longitud Total': longitud_total_linea,
                    'Porcentaje': porcentaje_avance
                })
    
    df_por_linea = pd.DataFrame(avance_por_linea)
    
    if not df_por_linea.empty:
        df_por_linea = df_por_linea.sort_values('Avance', ascending=True)
        
        df_por_linea['Label'] = df_por_linea.apply(
            lambda row: f"{row['Tipo de Línea']} ({row['Porcentaje']:.1f}%)", axis=1
        )
        
        fig_barras = px.bar(df_por_linea, x='Avance', y='Label',
                           orientation='h',
                           title='Avance Total por Tipo de Línea (con % de avance)',
                           labels={'Avance': 'Cantidad Total', 'Label': 'Tipo de Línea'},
                           text='Avance')
        
        fig_barras.update_traces(
            marker=dict(color='#ff7f0e'),
            texttemplate='%{text:.0f}',
            textposition='outside',
            hovertemplate='%{y}Avance: %{x}Longitud Total: %{customdata[0]:.1f} m',
            customdata=df_por_linea[['Longitud Total']].values
        )
        
        fig_barras.update_layout(
            height=400,
            paper_bgcolor='white',
            plot_bgcolor='rgba(240,240,240,0.5)',
            font=dict(family="Arial", size=12, color='#333333')
        )
        
        fig_barras = adaptar_grafico_mobile(fig_barras)
        st.plotly_chart(fig_barras, use_container_width=True, config=config_mobile)
        
        with st.expander("📊 Ver tabla de porcentajes de avance"):
            df_tabla_linea = df_por_linea[['Tipo de Línea', 'Avance', 'Longitud Total', 'Porcentaje']].copy()
            total_avance_tabla = df_tabla_linea['Avance'].sum()
            total_longitud_tabla = df_tabla_linea['Longitud Total'].sum()
            
            if total_longitud_tabla > 0:
                total_porcentaje = (total_avance_tabla / total_longitud_tabla) * 100
            else:
                total_porcentaje = 0
            
            df_tabla_linea['Avance'] = df_tabla_linea['Avance'].apply(lambda x: f"{int(x):,}")
            df_tabla_linea['Longitud Total'] = df_tabla_linea['Longitud Total'].apply(lambda x: f"{x:,.1f} m")
            df_tabla_linea['Porcentaje'] = df_tabla_linea['Porcentaje'].apply(lambda x: f"{x:.1f}%")
            
            fila_total = pd.DataFrame([{
                'Tipo de Línea': '📊 TOTAL',
                'Avance': f"{int(total_avance_tabla):,}",
                'Longitud Total': f"{total_longitud_tabla:,.1f} m",
                'Porcentaje': f"{total_porcentaje:.1f}%"
            }])
            
            df_tabla_linea = pd.concat([df_tabla_linea, fila_total], ignore_index=True)
            
            st.dataframe(
                df_tabla_linea,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Tipo de Línea": st.column_config.TextColumn("Tipo de Línea", width="medium"),
                    "Avance": st.column_config.TextColumn("Avance", width="small"),
                    "Longitud Total": st.column_config.TextColumn("Longitud Total", width="small"),
                    "Porcentaje": st.column_config.TextColumn("% Avance", width="small")
                }
            )

with col_right:
    avance_por_servicio = []
    for servicio in sorted(df_filtrado['Servicio'].dropna().unique()):
        avance_limpio = df_filtrado[df_filtrado['Servicio'] == servicio][fecha_cols].clip(lower=0).sum().sum()
        avance_por_servicio.append({'Servicio': servicio, 'Avance': avance_limpio})
    
    df_por_servicio = pd.DataFrame(avance_por_servicio)
    
    if not df_por_servicio.empty:
        df_por_servicio = df_por_servicio.sort_values('Avance', ascending=False)
        total_avance_servicio = df_por_servicio['Avance'].sum()
        
        if total_avance_servicio > 0:
            df_por_servicio['Porcentaje'] = (df_por_servicio['Avance'] / total_avance_servicio * 100).round(1)
        else:
            df_por_servicio['Porcentaje'] = 0
        
        df_por_servicio['Label'] = df_por_servicio.apply(
            lambda row: f"{row['Servicio']} ({row['Porcentaje']}%)", axis=1
        )
        
        fig_pie = px.pie(df_por_servicio,
                        values='Avance',
                        names='Label',
                        title='Distribución por Tamaño de Servicio',
                        hole=0.3)
        
        fig_pie.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='%{label}Avance: %{value}'
        )
        
        fig_pie.update_layout(
            height=400,
            showlegend=True,
            paper_bgcolor='white',
            font=dict(family="Arial", size=11, color='#333333')
        )
        
        fig_pie = adaptar_grafico_mobile(fig_pie)
        st.plotly_chart(fig_pie, use_container_width=True, config=config_mobile)

# Tabla detallada
st.markdown("---")
st.header("📋 Detalle por Tipo de Línea y Día")

tabla_resumen = []
for linea in df_filtrado['LINEA'].unique():
    if pd.notna(linea):
        df_linea = df_filtrado[df_filtrado['LINEA'] == linea]
        fila = {'Tipo de Línea': linea}
        total_linea = 0
        for i, fecha_col in enumerate(fecha_cols):
            valor = df_linea[fecha_col].clip(lower=0).sum()
            if valor > 0:
                fecha_corta = fecha_cols_display[i] if i < len(fecha_cols_display) else fecha_col
                fila[fecha_corta] = int(valor)
                total_linea += valor
        
        if total_linea > 0:
            fila['Total'] = int(total_linea)
            tabla_resumen.append(fila)

if tabla_resumen:
    df_tabla = pd.DataFrame(tabla_resumen)
    cols = [c for c in df_tabla.columns if c != 'Total']
    if 'Total' in df_tabla.columns:
        cols.append('Total')
    df_tabla = df_tabla[cols]
    st.dataframe(df_tabla, use_container_width=True, height=400)
else:
    st.info("No hay datos resumidos para mostrar.")

# Heatmap
st.markdown("---")
st.header("🔥 Mapa de Calor - Avance por Día y Tipo de Línea")

matriz_datos = []
tipos_linea_lista = []
for linea in df_filtrado['LINEA'].unique():
    if pd.notna(linea):
        df_linea = df_filtrado[df_filtrado['LINEA'] == linea]
        valores_dia = [df_linea[fecha_col].clip(lower=0).sum() for fecha_col in fecha_cols]
        if sum(valores_dia) > 0:
            matriz_datos.append(valores_dia)
            tipos_linea_lista.append(linea)

fig_heatmap = None

if matriz_datos:
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=matriz_datos,
        x=fecha_cols_display,
        y=tipos_linea_lista,
        colorscale='Blues',
        text=matriz_datos,
        texttemplate='%{text:.0f}',
        textfont={"size": 10},
        colorbar=dict(title="Avance"),
        hovertemplate='Línea: %{y}Fecha: %{x}Avance: %{z}'
    ))
    
    fig_heatmap.update_layout(
        title='Intensidad de Avance Diario',
        xaxis_title='Fecha (día/mes)',
        yaxis_title='Tipo de Línea',
        height=500,
        xaxis_tickangle=-45,
        paper_bgcolor='white',
        font=dict(family="Arial", size=11, color='#333333')
    )
    
    fig_heatmap = adaptar_grafico_mobile(fig_heatmap)
    st.plotly_chart(fig_heatmap, use_container_width=True, config=config_mobile)
else:
    st.info("No hay suficientes datos para generar el mapa de calor.")

# Progreso acumulado
st.markdown("---")
st.header("📊 Progreso Acumulado")

fig_acum = None

if not df_avance.empty:
    df_avance['Avance_Acumulado'] = df_avance['Avance'].cumsum()
    
    fig_acum = go.Figure()
    
    fig_acum.add_trace(go.Bar(
        x=df_avance['Fecha'],
        y=df_avance['Avance'],
        name='Avance Diario',
        marker_color='lightblue',
        text=df_avance['Avance'],
        texttemplate='%{text:.0f}',
        textposition='outside',
        hovertemplate='Fecha: %{x}Avance: %{y}'
    ))
    
    fig_acum.add_trace(go.Scatter(
        x=df_avance['Fecha'],
        y=df_avance['Avance_Acumulado'],
        name='Avance Acumulado',
        mode='lines+markers+text',
        line=dict(color='red', width=3),
        marker=dict(size=8),
        text=df_avance['Avance_Acumulado'],
        texttemplate='%{text:.0f}',
        textposition='top center',
        yaxis='y2',
        hovertemplate='Fecha: %{x}Acumulado: %{y}'
    ))
    
    fig_acum.update_layout(
        title='Avance Diario vs Avance Acumulado',
        xaxis_title='Fecha (día/mes)',
        yaxis_title='Avance Diario',
        yaxis2=dict(title='Avance Acumulado', overlaying='y', side='right'),
        height=400,
        hovermode='x unified',
        xaxis_tickangle=-45,
        paper_bgcolor='white',
        plot_bgcolor='rgba(240,240,240,0.5)',
        font=dict(family="Arial", size=12, color='#333333')
    )
    
    fig_acum = adaptar_grafico_mobile(fig_acum)
    fig_acum.update_layout(margin=dict(r=40))
    st.plotly_chart(fig_acum, use_container_width=True, config=config_mobile)

# Análisis por Servicio
st.markdown("---")
st.header("🔩 Detalle por Tamaño de Servicio y Día")

tabla_servicio = []
for servicio in sorted(df_filtrado['Servicio'].dropna().unique()):
    df_servicio = df_filtrado[df_filtrado['Servicio'] == servicio]
    fila = {'Servicio': servicio}
    total_servicio = 0
    for i, fecha_col in enumerate(fecha_cols):
        valor = df_servicio[fecha_col].clip(lower=0).sum()
        if valor > 0:
            fecha_corta = fecha_cols_display[i] if i < len(fecha_cols_display) else fecha_col
            fila[fecha_corta] = int(valor)
            total_servicio += valor
    
    if total_servicio > 0:
        fila['Total'] = int(total_servicio)
        tabla_servicio.append(fila)

if tabla_servicio:
    df_tabla_servicio = pd.DataFrame(tabla_servicio)
    cols = [c for c in df_tabla_servicio.columns if c != 'Total']
    if 'Total' in df_tabla_servicio.columns:
        cols.append('Total')
    df_tabla_servicio = df_tabla_servicio[cols]
    st.dataframe(df_tabla_servicio, use_container_width=True, height=400)
else:
    st.info("No hay datos resumidos por servicio para mostrar.")

# Tabla de datos completa
st.markdown("---")
st.header("📊 Datos Completos")

mostrar_todo = st.checkbox("Mostrar todas las columnas", value=False)

if mostrar_todo:
    st.dataframe(df_filtrado, use_container_width=True, height=400)
else:
    cols_principales = ['LINEA', 'Linea TAG', 'Servicio', 'Longitud Total (m)']
    cols_con_datos = [col for col in fecha_cols if df_filtrado[col].clip(lower=0).sum() > 0]
    cols_mostrar = cols_principales + cols_con_datos
    st.dataframe(df_filtrado[cols_mostrar], use_container_width=True, height=400)

# Estadísticas adicionales
st.markdown("---")
st.header("📈 Estadísticas Generales")

col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

with col_stat1:
    dias_con_trabajo = sum(1 for fecha_col in fecha_cols if df_filtrado[fecha_col].clip(lower=0).sum() > 0)
    st.metric("Días con Trabajo", dias_con_trabajo)

with col_stat2:
    if dias_con_trabajo > 0:
        promedio_diario = avance_total / dias_con_trabajo
        st.metric("Promedio Diario", f"{promedio_diario:,.0f}")
    else:
        st.metric("Promedio Diario", "N/A")

with col_stat3:
    if not df_avance.empty:
        dia_max = df_avance.loc[df_avance['Avance'].idxmax()]
        st.metric("Día Más Productivo", dia_max['Fecha'])
        st.caption(f"Avance: {int(dia_max['Avance'])}")
    else:
        st.metric("Día Más Productivo", "N/A")

with col_stat4:
    if avance_por_linea:
        linea_max = max(avance_por_linea, key=lambda x: x['Avance'])
        st.metric("Línea Más Avanzada", linea_max['Tipo de Línea'][:20] + "...")
        st.caption(f"Avance: {int(linea_max['Avance'])}")
    else:
        st.metric("Línea Más Avanzada", "N/A")

# ✅ SECCIÓN DE EXPORTACIÓN A PDF
st.markdown("---")
st.header("📥 Descargar Reporte")

if st.button("📄 Generar y Descargar PDF", key="btn_pdf", use_container_width=True):
    st.info("⏳ Generando PDF con gráficos de alta calidad... Por favor espera...")
    
    try:
        pdf_buffer = generar_pdf_reporte(
            df_filtrado, fecha_cols, fecha_cols_display,
            tipo_seleccionado, fig_linea, fig_barras, fig_pie,
            fig_heatmap, fig_acum
        )
        
        fecha_hora = datetime.now().strftime("%d%m%Y_%H%M%S")
        nombre_archivo = f"Reporte_Tuberia_{fecha_hora}.pdf"
        
        st.download_button(
            label="✅ Descargar PDF (Haz clic aquí)",
            data=pdf_buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True
        )
        
        st.success(f"✅ PDF generado exitosamente: {nombre_archivo}")
        st.info("💡 El archivo contiene:\n- ✓ Gráficos con colores preservados\n- ✓ Formato nítido y profesional\n- ✓ Todas las métricas y tablas\n- ✓ Mapas de calor y análisis detallado")
        
    except Exception as e:
        st.error(f"❌ Error al generar PDF: {str(e)}")
        st.warning("💡 Asegúrate de tener instaladas las dependencias:\n`pip install reportlab kaleido plotly`")

# Footer
st.markdown("---")
st.markdown("**Dashboard desarrollado para análisis de control de tubería por CPP ** | Última actualización: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
