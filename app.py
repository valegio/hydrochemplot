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
        #session['uploaded_data_file_path'] = os.path.join(app.config['UPLOAD_FOLDER'], data_filename)

        # Detect encoding txt file
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())

        # Read csv
        df = pd.read_csv(file_path, encoding=result['encoding'])

        # Format dataframe columns
        form_columns = ['Sample', 'Label', 'Color', 'Marker', 'Size', 'Alpha']

        piper_elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4"]
        schoeller_elements = ["Ca", "Mg", "Na", "K", "HCO3", "Cl", "SO4"]
        elements = ["Ca", "Mg", "Na", "K", "HCO3", "CO3", "Cl", "SO4",
                          "pH", "TDS"]


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
        for diagram in diagrams:
            if diagram == "Piper":
                piperdf = df.dropna(subset=piper_elements)
                piperdf = piperdf.reset_index(drop=True)
                triangle_piper.plot(piperdf, figname='static/output/trilinear_piper_plot', figformat='png')
                plt.legend(bbox_to_anchor=(1.15, 1), loc='best', borderaxespad=0.5, fontsize=8)
                plt.savefig('static/output/trilinear_piper_plot.png', bbox_inches="tight", dpi=300)

            if diagram == "Durov":
                durovdf = df.dropna(subset=elements)
                durovdf = durovdf.reset_index(drop=True)
                durovdf['TDS'] = [4000 if x > 4000 else x for x in durovdf['TDS']]
                print(durovdf)
                durvo.plot(durovdf, figname='static/output/durov_plot', figformat='png')
                plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=10)
                plt.savefig('static/output/durov_plot.png', bbox_inches="tight", dpi=300)


            if diagram == 'Schoeller':
                schoellerdf = df.dropna(subset=schoeller_elements)
                schoellerdf = schoellerdf.reset_index(drop=True)
                schoeller.plot(schoellerdf, figname='static/output/schoeller_plot', figformat='png')
                plt.legend(bbox_to_anchor=(1.05, 1), loc='best', borderaxespad=0.5, fontsize=6)
                plt.savefig('static/output/schoeller_plot.png', bbox_inches="tight", dpi=300)

        df.to_csv("static/output/output.csv", index=None)

        display_columns = ['Sample', 'Label']
        display_columns.extend(elements)
        # Dataframe into html table
        table = df[display_columns].to_html(classes='table table-stripped')

        return render_template("plot.html", diagrams = diagrams, table = table, titles=[''])

    return render_template("index.html")


def process_data(data, numeric_columns):

    #Replace '<' values by half of value
    for column in numeric_columns:
        data[column] = data[column].apply(under_detection)
        #data = data.dropna(subset = column)

    data[numeric_columns] = data[numeric_columns ].apply(pd.to_numeric)
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


#app.run()
if __name__ == '__main__':
    app.run(debug=True)
