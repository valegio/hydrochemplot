from flask import Flask, request, redirect, render_template, flash
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

plt.switch_backend('Agg')  # Backend no interactivo
matplotlib.rcParams['figure.max_open_warning'] = 0

app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = 'ChemPlot'

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

OUTPUT_FOLDER = os.path.join(app.static_folder, 'output')
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}


def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def read_file(file_path):
    """
    Lee un archivo CSV o Excel y retorna un DataFrame
    
    Args:
        file_path: Ruta al archivo
        
    Returns:
        DataFrame de pandas
    """
    file_extension = file_path.rsplit('.', 1)[1].lower()
    
    if file_extension == 'csv':
        # Detectar encoding para CSV
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        
        # Leer CSV con encoding detectado
        df = pd.read_csv(file_path, encoding=result['encoding'])
        
    elif file_extension in ['xlsx', 'xls']:
        # Leer archivo Excel
        df = pd.read_excel(file_path)
        
    else:
        raise ValueError(f"Formato de archivo no soportado: {file_extension}")
    
    return df


def validate_columns(df, required_columns, diagram_name):
    """
    Valida que el DataFrame contenga las columnas requeridas para un diagrama específico.
    
    Args:
        df: DataFrame a validar
        required_columns: Lista de columnas requeridas
        diagram_name: Nombre del diagrama para el mensaje de error
        
    Returns:
        tuple: (es_valido, columnas_faltantes)
    """
    missing_columns = [col for col in required_columns if col not in df.columns]
    return len(missing_columns) == 0, missing_columns


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == 'POST':

        # Check file uploaded
        file = request.files.get('file')
        if not file:
            flash('Suba un archivo CSV o Excel (.csv, .xlsx, .xls)', 'warning')
            return redirect("/")

        # Verificar extensión del archivo
        if not allowed_file(file.filename):
            flash('Suba un archivo CSV o Excel (.csv, .xlsx, .xls)', 'warning')
            return redirect("/")

        # Check if a checkbox was checked
        diagrams = request.form.getlist('diagram')
        if diagrams == []:
            flash('Seleccione un diagrama para graficar', 'warning')
            return redirect("/")

        # Save file
        data_filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], data_filename)
        file.save(file_path)

        # Read file (CSV or Excel)
        try:
            df = read_file(file_path)
        except Exception as e:
            flash(f'Error al leer el archivo: {str(e)}', 'warning')
            return redirect("/")

        # Define required columns for each diagram
        piper_elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4"]
        schoeller_elements = ["Ca", "Mg", "Na", "K", "HCO3", "Cl", "SO4"]
        durov_elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4", "pH", "TDS"]
        
        # Validate specific diagram requirements
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

        # If there are validation errors, show them and return
        if validation_errors:
            for error in validation_errors:
                flash(error, 'warning')
            flash('Verifique que el archivo tenga todas las columnas necesarias para los diagramas elegidos.', 'warning')
            return redirect("/")

        # Format dataframe columns
        form_columns = ['Sample', 'Label', 'Color', 'Marker', 'Size', 'Alpha']
        elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4", "pH", "TDS"]

        # Obtener los colormaps por separado
        tab20 = plt.get_cmap('tab20').colors
        tab20b = plt.get_cmap('tab20b').colors
        tab20c = plt.get_cmap('tab20c').colors
        
        # Combinarlos en una sola lista de colores
        combined_colors = np.vstack([tab20, tab20b, tab20c])
        
        # Crear un nuevo colormap
        extended_tab20 = ListedColormap(combined_colors, name='ExtendedTab20')
        
        # Verificar si el archivo trae columna 'Color'
        if 'Color' not in df.columns:
            # Asignar colores automáticamente basados en las etiquetas
            label_list = df['Label'].unique()
            n_colors_needed = len(label_list)
            
            if n_colors_needed <= 60:
                colors = [extended_tab20(i) for i in np.linspace(0, 1, n_colors_needed)]
            else:
                # Si necesitas más de 60 colores, usa otro colormap (ej. 'gist_rainbow')
                cmap = plt.get_cmap('gist_rainbow')
                colors = [cmap(i) for i in np.linspace(0, 1, n_colors_needed)]
            
            df['Color'] = df['Label'].map(dict(zip(label_list, colors)))
        else:
            invalid_colors = ~df['Color'].apply(lambda c: pd.isna(c) or mcolors.is_color_like(c))
            if invalid_colors.any():
                flash('Error en colores: algunos valores no son válidos (use nombres CSS, hex #RRGGBB o rgb(R,G,B))', 'warning')
                return redirect("/") 
            
        
        # Asignar valores fijos para las columnas que siempre se generan
        df['Marker'] = 'o'    
        df['Size'] = 60       
        df['Alpha'] = 0.6      
        
        # Procesar datos y seleccionar columnas
        df = process_data(df, elements)
        df = df[form_columns + elements]

        # Plot selected diagrams
        successful_plots = []
        
        for diagram in diagrams:
            try:
                if diagram == "Piper":
                    piperdf = df.dropna(subset=piper_elements)
                    if piperdf.empty:
                        flash(f'No se encontraron datos válidos para el diagrama Piper tras filtrar valores nulos', 'warning')
                        continue
                    fig = plt.figure(figsize=(10, 8))  # Crea una figura explícita
                    piperdf = piperdf.reset_index(drop=True)
                    triangle_piper.plot(piperdf, figname='static/output/trilinear_piper_plot', figformat='png')
                    plt.legend(bbox_to_anchor=(1.15, 1), loc='best', borderaxespad=0.5, fontsize=8)
                    plt.savefig('static/output/trilinear_piper_plot.png', bbox_inches="tight", dpi=150)
                    plt.close(fig)
                    successful_plots.append(diagram)

                elif diagram == "Durov":
                    durovdf = df.dropna(subset=durov_elements)
                    if durovdf.empty:
                        flash(f'No se encontraron datos válidos para el diagrama Durov tras filtrar valores nulos', 'warning')
                        continue
                    fig = plt.figure(figsize=(10, 8))  # Crea una figura explícita    
                    durovdf = durovdf.reset_index(drop=True)
                    durovdf['TDS'] = [4000 if x > 4000 else x for x in durovdf['TDS']]
                    print(durovdf)
                    durvo.plot(durovdf, figname='static/output/durov_plot', figformat='png')
                    plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=10)
                    plt.savefig('static/output/durov_plot.png', bbox_inches="tight", dpi=150)
                    plt.close(fig)
                    successful_plots.append(diagram)

                elif diagram == 'Schoeller':
                    schoellerdf = df.dropna(subset=schoeller_elements)
                    if schoellerdf.empty:
                        flash(f'No se encontraron datos válidos para el diagrama Schoeller tras filtrar valores nulos', 'warning')
                        continue
                    fig = plt.figure(figsize=(10, 8))  # Crea una figura explícita
                    schoellerdf = schoellerdf.reset_index(drop=True)
                    schoeller.plot(schoellerdf, figname='static/output/schoeller_plot', figformat='png')
                    plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=6)
                    plt.savefig('static/output/schoeller_plot.png', bbox_inches="tight", dpi=150)
                    plt.close(fig)
                    successful_plots.append(diagram)
                    
            except Exception as e:
                flash(f'Error creando el diagrama {diagram}: {str(e)}', 'error')

        # Check if any plots were successful
        if not successful_plots:
            flash('No se pudieron generar los diagramas. Por favor verifique el formato de sus datos.', 'error')
            return redirect("/")

        df.to_csv("static/output/output.csv", index=None)

        display_columns = ['Sample', 'Label']
        display_columns.extend(elements)
        # Dataframe into html table
        table = df[display_columns].to_html(classes='table table-stripped')

        return render_template("plot.html", diagrams=successful_plots, table=table, titles=[''])

    return render_template("index.html")


def process_data(data, numeric_columns):
    # Replace '<' values by half of value
    for column in numeric_columns:
        if column in data.columns:  # Solo procesar si la columna existe
            data[column] = data[column].apply(under_detection)

    # Only convert to numeric columns that exist in the dataframe
    existing_numeric_columns = [col for col in numeric_columns if col in data.columns]
    data[existing_numeric_columns] = data[existing_numeric_columns].apply(pd.to_numeric, errors='coerce')
    
    if 'CO3' in data.columns:
        data['CO3'] = data['CO3'].fillna(0)

    return data


def under_detection(value):
    value = str(value)
    if value.startswith('<'):
        return float(value[1:]) / 2
    try:
        value = float(value)
        return value
    except ValueError:
        return value


@app.route("/output")
def output():
    return render_template("plot.html")


@app.route("/instructions", methods=["GET"])
def instrucions():
    return render_template("instructions.html")


if __name__ == '__main__':
    app.run(debug=True)
