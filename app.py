from flask import Flask, request, redirect, render_template, flash
from wqchartpy import triangle_piper, durvo, schoeller
from werkzeug.utils import secure_filename
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import matplotlib
import chardet
import os


app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = 'ChemPlot'
matplotlib.use('Agg')

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


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
            flash('Please input a file', 'warning')
            return redirect("/")

        # Check if a checkbox was checked
        diagrams = request.form.getlist('diagram')
        if diagrams == []:
            flash('Please select a diagram to plot', 'warning')
            return redirect("/")

        # Save file
        data_filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], data_filename)
        file.save(file_path)

        # Detect encoding txt file
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())

        # Read csv
        try:
            df = pd.read_csv(file_path, encoding=result['encoding'])
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'warning')
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
            flash('Please ensure your CSV file contains all required columns for the selected diagrams.', 'warning')
            return redirect("/")

        # Format dataframe columns
        form_columns = ['Sample', 'Label', 'Color', 'Marker', 'Size', 'Alpha']
        elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4", "pH", "TDS"]

        df['Color'] = 'blue'
        df['Marker'] = 'o'
        df['Size'] = 60
        df['Alpha'] = 0.6

        # Process data
        df = process_data(df, elements)

        # Format dataframe for Wqchartpy
        form_columns.extend(elements)
        columns = form_columns
        df = df[columns]

        # Relate label to a color
        label_list = df['Label'].unique()
        cmap = plt.get_cmap('rainbow')
        colors = cmap(np.linspace(0, 1, len(label_list)))
        dictionary = dict(zip(label_list, colors))

        df['Color'] = df['Label'].map(dictionary)

        # Plot selected diagrams
        successful_plots = []
        
        for diagram in diagrams:
            try:
                if diagram == "Piper":
                    piperdf = df.dropna(subset=piper_elements)
                    if piperdf.empty:
                        flash(f'No valid data rows for Piper diagram after removing missing values', 'warning')
                        continue
                    piperdf = piperdf.reset_index(drop=True)
                    triangle_piper.plot(piperdf, figname='static/output/trilinear_piper_plot', figformat='png')
                    plt.legend(bbox_to_anchor=(1.15, 1), loc='best', borderaxespad=0.5, fontsize=8)
                    plt.savefig('static/output/trilinear_piper_plot.png', bbox_inches="tight", dpi=300)
                    successful_plots.append(diagram)

                elif diagram == "Durov":
                    durovdf = df.dropna(subset=durov_elements)
                    if durovdf.empty:
                        flash(f'No valid data rows for Durov diagram after removing missing values', 'warning')
                        continue
                    durovdf = durovdf.reset_index(drop=True)
                    durovdf['TDS'] = [4000 if x > 4000 else x for x in durovdf['TDS']]
                    print(durovdf)
                    durvo.plot(durovdf, figname='static/output/durov_plot', figformat='png')
                    plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=10)
                    plt.savefig('static/output/durov_plot.png', bbox_inches="tight", dpi=300)
                    successful_plots.append(diagram)

                elif diagram == 'Schoeller':
                    schoellerdf = df.dropna(subset=schoeller_elements)
                    if schoellerdf.empty:
                        flash(f'No valid data rows for Schoeller diagram after removing missing values', 'warning')
                        continue
                    schoellerdf = schoellerdf.reset_index(drop=True)
                    schoeller.plot(schoellerdf, figname='static/output/schoeller_plot', figformat='png')
                    plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=6)
                    plt.savefig('static/output/schoeller_plot.png', bbox_inches="tight", dpi=300)
                    successful_plots.append(diagram)
                    
            except Exception as e:
                flash(f'Error generating {diagram} diagram: {str(e)}', 'error')

        # Check if any plots were successful
        if not successful_plots:
            flash('No diagrams could be generated. Please check your data format.', 'error')
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
