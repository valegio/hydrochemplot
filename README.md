# Hydro Chem Plot

### Video Demo:  <https://youtu.be/CzIpBYMzL7s?si=wrA_nDwhzPac5-iL>

### Description:
Hydro Chem Plot is a web-based application designed to generate graphical diagrams for visualizing water geochemistry data. It supports the following diagrams:

+ **Trilinear Piper Diagram**
+ **Durov Diagram**
+ **Schoeller Diagram**

These diagrams are essential for interpreting the chemical composition of water samples, helping researchers and professionals in fields such as environmental science, hydrology, and engineering to make informed decisions. The app is developed in Python, utilizing the WQChartPy package for high-quality and customizable plotting.

**Importance of Each Diagram:**

**Trilinear Piper Diagram:** Frequently used to display the relative proportions of major cations and anions in water samples. It allows users to classify water types based on their chemical composition and can help identify processes such as mixing or ion exchange.

**Durov Diagram:** A modification of the Piper diagram that adds pH and total dissolved solids (TDS) information, making it useful for identifying water quality issues and chemical relationships.

**Schoeller Diagram:** Often used to compare the concentrations of different ions across multiple samples, making it valuable for longitudinal studies or comparing water sources.

### How to use:

#### File requirements
+ Input file must be a comma-separated values (CSV) file.
+ Supported units: mg/L or ppm.
+ Required identification columns: 'Sample' and 'Label'.
+ For the Trilinear Piper diagram, the following geochemical parameters are required: 'Ca', 'Mg', 'Na', 'K', 'HCO3', 'CO3', 'Cl', and 'SO4'.
+ For the Durov diagram, the required parameters are: 'Ca', 'Mg', 'Na', 'K', 'HCO3', 'CO3', 'Cl', 'SO4', 'pH', and 'TDS'.
+ For the Schoeller diagram, the required parameters are: 'Ca', 'Mg', 'Na', 'K', 'Cl', 'SO4', and 'HCO3'.

#### Instructions

1. Upload a CSV file.
2. Select the diagrams you wish to generate.
3. Submit your request and wait for the processing.
4. To download the generated figure, right-click on the image and select "Save image as...".

### Project Content:

#### app.py

This Python script handles the CSV file upload and generates the selected diagrams. The steps involved are:
1. **File Check:** Verifies if a CSV file has been uploaded. If not, a warning is displayed.
2. **Diagram Selection:** Checks if any diagrams (Trilinear Piper, Durov, or Schoeller) have been selected. If no diagrams are selected, a warning prompts the user to select one.
3. **File Storage:** The uploaded CSV file is saved in the /static/uploads/ directory.
4. **Data Processing:**
+ Values below the detection limit are replaced by half of their value. For example, "<0.0001" 	becomes "0.00005".
+ Missing values in the 'CO3' column are filled with "0".
5. **Color Assignment:** Assigns a unique color to each distinct 'Label'.
6. **Diagram Generation:** For each selected diagram, the script:
+ Removes data rows that lack required geochemical parameters (see "File Requirements").
+ Generates the diagram using the WQChartPy package.
+ Configures the legend to appear outside the figure, on the right-hand side.
+ Saves the resulting figure in the /static/output/ directory.

For the Durov diagram, the 'TDS' axis is capped at 4000 ppm to avoid scaling issues caused by high TDS concentrations. If a sample exceeds 4000 ppm, it is represented as 4000 ppm. This ensures the diagram remains readable without compressing the rest of the figure.
Additionally, a simplified HTML table is generated to display the data before any rows with missing values are removed.

#### layout.html
This HTML file defines the layout structure of the app, including the navigation bar, which allows access to the instructions and main page. It serves as the base template for all other HTML files.

#### instructions.html
This page contains detailed information on the file format requirements and usage instructions. It includes an example of a valid CSV file, along with sample diagrams generated from that data. Each type of diagram is accompanied by a brief explanation of its geochemical significance.

#### index.html
The main page of the web app. Here, users can upload their CSV file and select which diagrams (Trilinear Piper, Durov, or Schoeller) to generate. The page includes a form that only accepts CSV files. Once the user has uploaded a file and selected the desired diagrams, they can click the "Submit" button to process the data.
If the uploaded file is invalid or no diagrams are selected, the app will display an appropriate warning message.

#### plot.html
This page displays the generated diagrams alongside a single summary table of the uploaded data. Rather than showing separate tables for each diagram, which would require different sets of geochemical parameters, a single consolidated table is shown. This table includes all data prior to filtering out rows with missing values required for specific diagrams.

### Conclusion:
Hydro Chem Plot simplifies the process of visualizing complex water geochemistry data, providing three distinct types of diagrams commonly used in hydrochemistry studies. The intuitive web interface and streamlined workflow allow users to quickly generate and download high-quality diagrams from their CSV files.
