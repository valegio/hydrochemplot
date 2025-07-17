from flask import Flask, request, redirect, render_template, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from wqchartpy import triangle_piper, durvo, schoeller
from werkzeug.utils import secure_filename
import gc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.colors import ListedColormap
import pandas as pd
import numpy as np
import chardet
import os
import logging
from datetime import datetime

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

plt.switch_backend('Agg')
matplotlib.rcParams['figure.max_open_warning'] = 0

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Rate limiting (máximo 30 requests por minuto)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["30 per minute"]
)

# Límite de tamaño de archivo (16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Configuración original
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Contador simple
chart_counter = {
    'Piper': 0,
    'Durov': 0,
    'Schoeller': 0,
    'total': 0
}

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

OUTPUT_FOLDER = os.path.join(app.static_folder, 'output')
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_safe_filename(filename):
    """Verifica que el nombre del archivo sea seguro"""
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    return not any(char in filename for char in dangerous_chars)

def read_file(file_path):
    """Lee un archivo CSV o Excel y retorna un DataFrame"""
    file_extension = file_path.rsplit('.', 1)[1].lower()
    
    try:
        if file_extension == 'csv':
            # Detectar encoding para CSV
            with open(file_path, 'rb') as f:
                result = chardet.detect(f.read())
            
            encoding = result['encoding'] if result['confidence'] > 0.7 else 'utf-8'
            df = pd.read_csv(file_path, encoding=encoding)
            
        elif file_extension in ['xlsx', 'xls']:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Formato no soportado: {file_extension}")
        
        # Limitar filas para prevenir ataques DoS
        if len(df) > 5000:
            logger.warning(f"Archivo muy grande ({len(df)} filas), limitando a 5000")
            df = df.head(5000)
        
        return df
        
    except Exception as e:
        logger.error(f"Error leyendo archivo: {e}")
        raise

def validate_columns(df, required_columns, diagram_name):
    """Valida que el DataFrame contenga las columnas requeridas"""
    missing_columns = [col for col in required_columns if col not in df.columns]
    return len(missing_columns) == 0, missing_columns

def clean_temp_files():
    """Limpia archivos temporales antiguos"""
    try:
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            # Eliminar archivos más antiguos de 1 hora
            if os.path.getctime(filepath) < (datetime.now().timestamp() - 3600):
                os.remove(filepath)
                logger.info(f"Archivo temporal eliminado: {filename}")
    except Exception as e:
        logger.error(f"Error limpiando archivos temporales: {e}")

@app.route("/", methods=["GET", "POST"])
@limiter.limit("10 per minute")  # Máximo 10 uploads por minuto
def index():
    if request.method == 'POST':
        try:
            # Limpiar archivos temporales
            clean_temp_files()
            
            # Validar archivo
            file = request.files.get('file')
            if not file or file.filename == '':
                flash('Suba un archivo CSV o Excel (.csv, .xlsx, .xls)', 'warning')
                return redirect("/")

            # Validaciones de seguridad adicionales
            if not allowed_file(file.filename):
                flash('Tipo de archivo no permitido', 'warning')
                return redirect("/")
                
            if not is_safe_filename(file.filename):
                flash('Nombre de archivo no válido', 'warning')
                return redirect("/")

            # Validar diagramas
            diagrams = request.form.getlist('diagram')
            if diagrams == []:
                flash('Seleccione un diagrama para graficar', 'warning')
                return redirect("/")

            # Nombre de archivo seguro
            original_filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{timestamp}_{original_filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
            
            file.save(file_path)

            # Leer archivo
            try:
                df = read_file(file_path)
            except Exception as e:
                os.remove(file_path) 
                flash('Error al procesar el archivo. Verifique el formato.', 'warning')
                logger.error(f"Error leyendo archivo: {e}")
                return redirect("/")

            # Validaciones de columnas 
            piper_elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4"]
            schoeller_elements = ["Ca", "Mg", "Na", "K", "HCO3", "Cl", "SO4"]
            durov_elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4", "pH", "TDS"]
            
            validation_errors = []
            
            for diagram in diagrams:
                if diagram == "Piper":
                    is_valid, missing_cols = validate_columns(df, piper_elements, "Piper")
                    if not is_valid:
                        validation_errors.append(f'Piper diagram requires missing columns: {", ".join(missing_cols)}')
                
                elif diagram == "Durov":
                    is_valid, missing_cols = validate_columns(df, durov_elements, "Durov")
                    if not is_valid:
                        validation_errors.append(f'Durov diagram requires missing columns: {", ".join(missing_cols)}')
                
                elif diagram == 'Schoeller':
                    is_valid, missing_cols = validate_columns(df, schoeller_elements, "Schoeller")
                    if not is_valid:
                        validation_errors.append(f'Schoeller diagram requires missing columns: {", ".join(missing_cols)}')

            if validation_errors:
                os.remove(file_path)  # Limpiar archivo
                for error in validation_errors:
                    flash(error, 'warning')
                flash('Verifique que el archivo tenga todas las columnas necesarias para los diagramas elegidos.', 'warning')
                return redirect("/")

            # Procesamiento de datos 
            form_columns = ['Sample', 'Label', 'Color', 'Marker', 'Size', 'Alpha']
            elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4", "pH", "TDS"]

            # Colores 
            tab20 = plt.get_cmap('tab20').colors
            tab20b = plt.get_cmap('tab20b').colors
            tab20c = plt.get_cmap('tab20c').colors
            combined_colors = np.vstack([tab20, tab20b, tab20c])
            extended_tab20 = ListedColormap(combined_colors, name='ExtendedTab20')
            
            if 'Color' not in df.columns:
                label_list = df['Label'].unique()
                n_colors_needed = len(label_list)
                
                if n_colors_needed <= 60:
                    colors = [extended_tab20(i) for i in np.linspace(0, 1, n_colors_needed)]
                else:
                    cmap = plt.get_cmap('gist_rainbow')
                    colors = [cmap(i) for i in np.linspace(0, 1, n_colors_needed)]
                
                df['Color'] = df['Label'].map(dict(zip(label_list, colors)))
            else:
                invalid_colors = ~df['Color'].apply(lambda c: pd.isna(c) or mcolors.is_color_like(c))
                if invalid_colors.any():
                    os.remove(file_path)
                    flash('Error en colores: algunos valores no son válidos', 'warning')
                    return redirect("/") 
                
            df['Marker'] = 'o'    
            df['Size'] = 60       
            df['Alpha'] = 0.6      
            
            df = process_data(df, elements)
            df = df[form_columns + elements]

            # Generar gráficos
            successful_plots = []
            
            for diagram in diagrams:
                try:
                    if diagram == "Piper":
                        piperdf = df.dropna(subset=piper_elements)
                        if piperdf.empty:
                            flash(f'No hay datos válidos para el diagrama Piper', 'warning')
                            continue
                        fig = plt.figure(figsize=(10, 8))
                        piperdf = piperdf.reset_index(drop=True)
                        triangle_piper.plot(piperdf, figname='static/output/trilinear_piper_plot', figformat='png')
                        plt.legend(bbox_to_anchor=(1.15, 1), loc='best', borderaxespad=0.5, fontsize=8)
                        plt.savefig('static/output/trilinear_piper_plot.png', bbox_inches="tight", dpi=150)
                        plt.close(fig)
                        successful_plots.append(diagram)
                        chart_counter['Piper'] += 1
                        chart_counter['total'] += 1

                    elif diagram == "Durov":
                        durovdf = df.dropna(subset=durov_elements)
                        if durovdf.empty:
                            flash(f'No hay datos válidos para el diagrama Durov', 'warning')
                            continue
                        fig = plt.figure(figsize=(10, 8))
                        durovdf = durovdf.reset_index(drop=True)
                        durovdf['TDS'] = [4000 if x > 4000 else x for x in durovdf['TDS']]
                        durvo.plot(durovdf, figname='static/output/durov_plot', figformat='png')
                        plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=10)
                        plt.savefig('static/output/durov_plot.png', bbox_inches="tight", dpi=150)
                        plt.close(fig)
                        successful_plots.append(diagram)
                        chart_counter['Durov'] += 1
                        chart_counter['total'] += 1

                    elif diagram == 'Schoeller':
                        schoellerdf = df.dropna(subset=schoeller_elements)
                        if schoellerdf.empty:
                            flash(f'No hay datos válidos para el diagrama Schoeller', 'warning')
                            continue
                        fig = plt.figure(figsize=(10, 8))
                        schoellerdf = schoellerdf.reset_index(drop=True)
                        schoeller.plot(schoellerdf, figname='static/output/schoeller_plot', figformat='png')
                        plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=6)
                        plt.savefig('static/output/schoeller_plot.png', bbox_inches="tight", dpi=150)
                        plt.close(fig)
                        successful_plots.append(diagram)
                        chart_counter['Schoeller'] += 1
                        chart_counter['total'] += 1
                        
                except Exception as e:
                    logger.error(f'Error creando diagrama {diagram}: {e}')
                    flash(f'Error creando el diagrama {diagram}', 'error')

            # Limpiar archivo temporal después de procesarlo
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error eliminando archivo temporal: {e}")

            if not successful_plots:
                flash('No se pudieron generar los diagramas. Verifique el formato de sus datos.', 'error')
                return redirect("/")

            df.to_csv("static/output/output.csv", index=None)

            display_columns = ['Sample', 'Label']
            display_columns.extend(elements)
            table = df[display_columns].to_html(classes='table table-stripped')

            return render_template("plot.html", diagrams=successful_plots, table=table, titles=[''])

        except Exception as e:
            logger.error(f"Error no controlado: {e}")
            flash('Error procesando la solicitud. Intente nuevamente.', 'error')
            return redirect("/")

    # GET request - mostrar página principal con contador
    return render_template("index.html", stats=chart_counter)

# Endpoint para ver estadísticas
@app.route("/stats")
def stats():
    """Página para ver estadísticas de uso"""
    return render_template("stats.html", stats=chart_counter)

# Funciones originales
def process_data(data, numeric_columns):
    for column in numeric_columns:
        if column in data.columns:
            data[column] = data[column].apply(under_detection)

    existing_numeric_columns = [col for col in numeric_columns if col in data.columns]
    data[existing_numeric_columns] = data[existing_numeric_columns].apply(pd.to_numeric, errors='coerce')
    
    if 'CO3' in data.columns:
        data['CO3'] = data['CO3'].fillna(0)

    return data

def under_detection(value):
    value = str(value)
    if value.startswith('<'):
        try:
            return float(value[1:]) / 2
        except ValueError:
            return value
    try:
        value = float(value)
        return value
    except ValueError:
        return value

@app.route("/output")
def output():
    return render_template("plot.html")

@app.route("/instructions", methods=["GET"])
def instructions():
    return render_template("instructions.html")

# Manejo de errores
@app.errorhandler(413)
def too_large(e):
    flash('El archivo es demasiado grande (máximo 16MB)', 'error')
    return redirect("/")

@app.errorhandler(429)
def ratelimit_handler(e):
    flash('Demasiadas solicitudes. Espere un momento antes de intentar nuevamente.', 'error')
    return redirect("/")

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode)
