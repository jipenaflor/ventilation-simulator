# Ventilation Simulator
A web application that performs indoor simulation of natural ventilation using OpenFOAM and ParaView. It utilized trame, a Python integration framewok by Kitware, and was built to run only at a development server from the UP-EEEI HPC cluster.

## Features of the Application
### Set Environment Control Panel
1. Binary STL Files Upload Form
   
   The widget allows the user to upload multiple binary STL files that make up the structures of his environment. It interfaces with the ParaView widget to render the geometries, as well as their dimensions.

   <p align="center">
      <img src="https://github.com/jipenaflor/ventilation-simulator/assets/124503188/3ee2e5b9-39d6-48e7-b79a-a8fcb0d24458">
   </p>
   
2. Input Fields for Boundary Setting and Menu for Patch Selection
   
   The input fields prompt the user to input data of type positive number. The inputs serve as the dimensions of the block that determines the boundaries of simulation. The menu allows the user to specify as to which side of the block will the airflow come in (inlet) and out (outlet).

   <p align="center">
      <img src="https://github.com/jipenaflor/ventilation-simulator/assets/124503188/eec502a9-a70a-4be1-9124-0e0978556aed">
   </p>

4. Button to Set the Environment

   The widget is locked until all the inputs are valid, i.e., there are uploaded binary STL files and valid input dimensions. When clicked, it runs the necessary OpenFOAM operations to convert the uploaded geometries and set the user environment with the specified properties. When the processes are done, the resulting environment is rendered in the ParaView widget.

   <p align="center">
      <img src="https://github.com/jipenaflor/ventilation-simulator/assets/124503188/13d66726-514f-404d-9240-c077dc46ff11">
   </p>

### Simulate Airflow Control Panel
1. Input Fields for Atmospheric Boundary Layer Setting
  
   The input fields prompt the user to set a valid mean wind speed at a certain height.
   
2. Menu for Landscape Description
  
   The widget allows the user to set the aerodynamic roughness length by landscape description that follows the Davenport-Wieringa roughness classification.

3. Input Field for Simulation Time
   
   The input field prompts the user to set a valid time of airflow in the environment.

   <p align="center">
      <img src="https://github.com/jipenaflor/ventilation-simulator/assets/124503188/c1c497bc-7fbd-44e2-8231-146338cb3550">
   </p>
   
4. Button to Simulate Airflow
   
   The widget is locked until all the inputs are valid. When clicked, it runs the necessary OpenFOAM operations to run simpleFoam, a steady-state incompressible, turbulent flow solver. When the processes are done, the simulation results with applied slice filter for further analysis is rendered in the ParaView widget.

7. Slider to Interact with the Results
  
   The widget allows the user to oscillate the slice filter to examine the airflow at a certain height of the room.

   <p align="center">
      <img src="https://github.com/jipenaflor/ventilation-simulator/assets/124503188/d83014cc-95ba-492d-a86e-f0abf4050ab4">
   </p>

