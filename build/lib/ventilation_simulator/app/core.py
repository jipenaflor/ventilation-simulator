"""
Define your classes and create the instances that you need to expose
"""
import paraview.web.venv  # Available in PV 5.10
import os
import subprocess
import shutil
import tempfile
import logging
import asyncio

from trame.app import get_server, asynchronous
from trame.widgets import vuetify, paraview
from trame.ui.vuetify import SinglePageWithDrawerLayout
from trame.widgets import vtk, vuetify, trame


from paraview import simple


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------
# Engine class
# ---------------------------------------------------------


class Engine:
    def __init__(self, server=None):
        if server is None:
            server = get_server()

        self._server = server

        # initialize state + controller
        state, ctrl = server.state, server.controller

        # Set title
        state.trame__title = "Ventilation Simulator"

        # Bind instance methods to controller
        ctrl.on_server_reload = self.ui

        # Bind instance methods to state change
        state.change("files")(self.read)
        state.change("myLength")(self.set_length)
        state.change("myWidth")(self.set_width)
        state.change("myHeight")(self.set_height)
        state.change("inlet")(self.set_inlet)
        state.change("outlet")(self.set_outlet)

        state.change("myWindSpeed")(self.set_windSpeed)
        state.change("myWindHeight")(self.set_windHeight)
        state.change("aeroRoughness")(self.set_aeroRoughness)
        state.change("mySimTime")(self.set_simTime)

        # Create temporary directory for uer simulation
        self.user = tempfile.TemporaryDirectory(dir='./')
        shutil.copytree('./simulation', self.user.name, dirs_exist_ok=True)
        self.USER_DIR = self.user.name

        # Initialize internal and state variables
        
        self.FILENAME = ""
        self.USER_STL = ""
        self.DEFAULT_VALUE = 5
        '''
        state.length = ""
        state.width = ""
        state.height = ""
        '''
        self.inlet = ""
        self.outlet = ""
        
        self.toSet = False
        self.setSuccess = False
        #state.setProgress = 0
        '''
        state.windSpeed = ""
        state.windHeight = ""
        '''
        self.windDirection = ""
        self.aeroRoughness = ""
        #state.simTime = ""
        self.toSimulate = False

        # Initialize Pipeline Widget
        state.setdefault("active_ui", "environment")

        # Initialize ParaView
        self.view = simple.GetRenderView()
        self.view = simple.Render()

        # Generate UI
        self.ui()

    @property
    def server(self):
        return self._server

    @property
    def state(self):
        return self.server.state

    @property
    def ctrl(self):
        return self.server.controller

    def show_in_jupyter(self, **kwargs):
        from trame.app import jupyter

        logger.setLevel(logging.WARNING)
        jupyter.show(self.server, **kwargs)

    # Methods for Environment Setting
    class Patch:
        front = 0
        back = 1
        left = 2
        right = 3
    
    class Landscape:
        open = 0
        negligible = 1
        minimal = 2
        occassional = 3
        scattered = 4
        large = 5
        homogeneous = 6
        varying = 7

    def read(self, files, **kwargs):
        if files is None or len(files) == 0:
            return

        for file in files:
            self.FILENAME = file.get("name")
            self.USER_STL = file.get("content")
        
        save_path = os.path.join(self.USER_DIR, 'constant', 'triSurface', self.FILENAME)
        
        with  open(save_path, "wb") as fw:
            fw.write(self.USER_STL)
        fw.close()
    
    def validate_number(self, myNumber):
        try:
            valid = float(myNumber)
            return (valid > 0)
        except:
            logger.info("User puts an invalid input")
    
    def set_length(self, myLength, **kwargs):
        isPositive = self.validate_number(myLength)
        if isPositive:
            self.state.length = float(myLength)
            self.toSet = True
            return
        self.toSet = False
    
    def set_width(self, myWidth, **kwargs):
        isPositive = self.validate_number(myWidth)
        if isPositive:
            self.state.width = float(myWidth)
            self.toSet = True
            return
        self.toSet = False
    
    def set_height(self, myHeight, **kwargs):
        isPositive = self.validate_number(myHeight)
        if isPositive:
            self.state.height = float(myHeight)
            self.toSet = True
            return
        self.toSet = False
    
    def set_inlet(self, inlet, **kwargs):
        if inlet == self.Patch.front:
            self.inlet = "(0 1 5 4)"
            self.windDirection = "(0 1 0)"
        elif inlet == self.Patch.back:
            self.inlet = "(3 7 6 2)"
            self.windDirection = "(0 1 0)"
        elif inlet == self.Patch.left:
            self.inlet = "(0 4 7 3)"
            self.windDirection = "(1 0 0)"
        elif inlet == self.Patch.right:
            self.inlet = "(1 2 6 5)"
            self.windDirection = "(1 0 0)"

    def set_outlet(self, outlet, **kwargs):
        if outlet == self.Patch.front:
            self.outlet = "(0 1 5 4)"
        elif outlet == self.Patch.back:
            self.outlet = "(3 7 6 2)"
        elif outlet == self.Patch.left:
            self.outlet = "(0 4 7 3)"
        elif outlet == self.Patch.right:
            self.outlet= "(1 2 6 5)"

    def convert(self, **kwargs):
        conversion_path = os.path.join(self.USER_DIR, 'system', 'surfaceFeaturesDict')
        with open(conversion_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()

        line[15] = "surfaces (\"" + str(self.FILENAME) + "\");\n"

        with open(conversion_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)

        toEmesh = subprocess.Popen('surfaceFeatures', cwd=self.USER_DIR)
        toEmesh.wait()
    
    def block(self, **kwargs):
        # Modify blockMesh
        x = self.state.length
        y = self.state.width
        z = self.state.height
        vertices = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), \
                    (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]

        block_path = os.path.join(self.USER_DIR, 'system', 'blockMeshDict')

        with open(block_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()

        i = 19
        while i < 25:
            for v in vertices:
                line[i] = "    (" + str(v[0]) + " " + str(v[1]) + " " + str(v[2]) + ")\n"
                i+=1
        
        line[46] = "            " + self.inlet + "\n"
        line[63] = "            " + self.outlet + "\n" 

        patches_val = ["(0 1 5 4)", "(3 7 6 2)", "(0 4 7 3)", "(1 2 6 5)"]
        patches_val.remove(self.inlet)
        patches_val.remove(self.outlet)

        line[54] = "            " + patches_val[0] + "\n"
        line[55] = "            " + patches_val[1] + "\n"

        with open(block_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)
        
        # Modify Coefficients
        stl_name = os.path.splitext(self.FILENAME)[0]
        coeff = ["epsilon", "k", "nut", "p", "U"]
        for f in coeff:
            coeff_path = os.path.join(self.USER_DIR, '0', f)
            with open(coeff_path, "r", encoding="utf-8") as fr:
                line = fr.readlines()
            line[24] = "    " + stl_name + "\n"
            with open(coeff_path, "w", encoding="utf-8") as fw:
                fw.writelines(line)  
        
        toBlock = subprocess.Popen("blockMesh", cwd=self.USER_DIR)
        toBlock.wait()
    
    def mesh(self, **kwargs):
        stl_name = os.path.splitext(self.FILENAME)[0]
        mesh_path = os.path.join(self.USER_DIR, 'system', 'snappyHexMeshDict')

        with open(mesh_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()

        line[30] = "    " + stl_name + "\n"
        line[33] = "        file \"" + self.FILENAME + "\";\n"
        line[87] = "            file \"" + stl_name + ".eMesh\";\n"
        line[105] = "        " + stl_name + "\n"
        line[147] = "        " + self.FILENAME + "\n"
        line[222] = "	" + stl_name + "\n"

        with open(mesh_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)

        commands = [['decomposePar', '-force'], ['mpirun', '-np', '12', 'snappyHexMesh', '-parallel', '-overwrite'], ['reconstructParMesh', '-constant']]
        
        for cmd in commands:
            process = subprocess.Popen(cmd, cwd=self.USER_DIR)
            process.wait()
    
    def view_stl(self, **kwargs):
        toFoam = subprocess.Popen(['paraFoam', '-builtin', '-touch'], cwd=self.USER_DIR)
        toFoam.wait()

        foam_file = self.USER_DIR + ".foam"
        foam_path = os.path.join(self.USER_DIR, foam_file)
        reader = simple.OpenFOAMReader(FileName=foam_path)
        environment = simple.Show(reader, self.view)
        environment.Opacity = 0.3
        simple.SetActiveSource(environment)
        self.view.AxesGrid.Visibility = 1
        self.ctrl.view_reset_camera()
        self.ctrl.view_update()
    
    def update_setProgress(self, delta):
        with self.state:
            self.state.setProgress += delta

    @asynchronous.task
    async def _async_set(self, **kwargs):
        self.convert()
        self.update_setProgress(5)
        await asyncio.sleep(0.01)
        self.block()
        self.update_setProgress(15)
        await asyncio.sleep(0.01)
        self.mesh()
        self.update_setProgress(75)
        await asyncio.sleep(0.05)
        self.view_stl()
        self.update_setProgress(5)
        await asyncio.sleep(0.05)
        self.setSuccess = True
        with self.state:
            self.state.set_running = False
    
    def run_set(self, **kwargs):
        if self.inlet != self.outlet:
            if self.toSet:
                self.state.set_running = True
                asynchronous.create_task(self._async_set())

    def set_windSpeed(self, myWindSpeed, **kwargs):
        isPositive = self.validate_number(myWindSpeed)
        if isPositive and self.setSuccess:
            self.state.windSpeed = myWindSpeed
            self.toSimulate = True
            return
        self.toSimulate = False
    
    def set_windHeight(self, myWindHeight, **kwargs):
        isPositive = self.validate_number(myWindHeight)
        if isPositive and self.setSuccess:
            self.state.windHeight = myWindHeight
            self.toSimulate = True
            return
        self.toSimulate = False

    def set_aeroRoughness(self, aeroRoughness, **kwargs):
        if aeroRoughness == self.Landscape.open:
            self.aeroRoughness = "0.0002"
        elif aeroRoughness == self.Landscape.negligible:
            self.aeroRoughness = "0.005"
        elif aeroRoughness == self.Landscape.minimal:
            self.aeroRoughness = "0.03"
        elif aeroRoughness == self.Landscape.occassional:
            self.aeroRoughness = "0.10"
        elif aeroRoughness == self.Landscape.scattered:
            self.aeroRoughness = "0.25"
        elif aeroRoughness == self.Landscape.large:
            self.aeroRoughness = "0.5"
        elif aeroRoughness == self.Landscape.homogeneous:
            self.aeroRoughness = "1.0"
        elif aeroRoughness == self.Landscape.varying:
            self.aeroRoughness = "2.0"
    
    def set_simTime(self, mySimTime, **kwargs):
        isPositive = self.validate_number(mySimTime)
        if isPositive and self.setSuccess:
            self.state.simTime = mySimTime
            self.toSimulate = True
            return
        self.toSimulate = False

    def simplefoam(self, **kwargs):
        # modify ABLConditions Dict
        ABL_path = os.path.join(self.USER_DIR, '0', 'include', 'ABLConditions')
        with open(ABL_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()
        
        line[8] = "Uref                 " + self.state.windSpeed + ";\n"
        line[9] = "Zref                 " + self.state.windHeight + ";\n"
        line[11] = "flowDir              " + self.windDirection + ";\n"
        line[12] = "z0                   uniform " + self.aeroRoughness + ";\n"

        with open(ABL_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)
        
            # modify controlDict
        control_path = os.path.join(self.USER_DIR, 'system', 'controlDict')
        with open(control_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()
        
        line[23] = "endTime         " + self.state.simTime + ";\n"
        line[29] = "writeInterval   " + self.state.simTime + ";\n"

        with open(control_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)
        
            # modify decomposeParDict
        decompose_path = os.path.join(self.USER_DIR, 'system', 'decomposeParDict.orig')
        with open(decompose_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()
        
        line[18] = "method          scotch;\n"

        with open(decompose_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)
        
            # run simulation
        commands = [['decomposePar', '-force'], ['mpirun', '-np', '12', 'simpleFoam', '-parallel'], \
                    ['reconstructPar'], ['paraFoam', '-builtin', '-touch']]
        for cmd in commands:
            process = subprocess.Popen(cmd, cwd=self.USER_DIR)
            process.wait()
    
    def view_foam(self, **kwargs):
        stl_path = os.path.join(self.USER_DIR, 'constant', 'triSurface', self.FILENAME)
        foam_file = self.USER_DIR + ".foam"
        foam_path = os.path.join(self.USER_DIR, foam_file)

        stl_reader = simple.STLReader(FileNames=[stl_path])
        environment = simple.Show(stl_reader, self.view, 'GeometryRepresentation')
        environment.Opacity = 0.25

        foam_reader = simple.OpenFOAMReader(FileName=foam_path)
        foam_reader.MeshRegions = ['internalMesh']
        foam_reader.CellArrays = ['U']
        airflow = simple.Show(foam_reader, self.view, 'UnstructuredGridRepresentation')
        
        simple.SetActiveSource(environment)
        simple.SetActiveSource(airflow)
        animationScene = simple.GetAnimationScene()
        animationScene.UpdateAnimationUsingDataTimeSteps()

        airflow.ScaleTransferFunction.Points = [-4.672417163848877, 0.0, 0.5, 0.0, 4.776854038238525, 1.0, 0.5, 0.0]
        airflow.OpacityTransferFunction.Points = [-4.672417163848877, 0.0, 0.5, 0.0, 4.776854038238525, 1.0, 0.5, 0.0]
        simple.ColorBy(airflow, ('POINTS', 'U', 'Magnitude'))
        airflow.RescaleTransferFunctionToDataRange(True, False)
        airflow.SetScalarBarVisibility(self.view, True)
        self.view.Update()

        uTF2D = simple.GetTransferFunction2D('U')

        # get color transfer function/color map for 'U'
        uLUT = simple.GetColorTransferFunction('U')
        uLUT.TransferFunction2D = uTF2D
        uLUT.RGBPoints = [0.0, 0.231373, 0.298039, 0.752941, 3.1018124603982984, 0.865003, 0.865003, 0.865003, 6.203624920796597, 0.705882, 0.0156863, 0.14902]
        uLUT.ScalarRangeInitialized = 1.0

        # get opacity transfer function/opacity map for 'U'
        uPWF = simple.GetOpacityTransferFunction('U')
        uPWF.Points = [0.0, 0.0, 0.5, 0.0, 6.203624920796597, 1.0, 0.5, 0.0]
        uPWF.ScalarRangeInitialized = 1

        # Create slice
        slice = simple.Slice(Input=foam_reader)
        slice.SliceType = 'Plane'
        slice.HyperTreeGridSlicer = 'Plane'
        slice.SliceOffsetValues = [0.0]
        slice.SliceType.Origin = [0.0, 0.0, float(self.state.windHeight)]
        slice.SliceType.Normal = [0.0, 0.0, 1.0]

        airflow_slice = simple.Show(slice, self.view, 'GeometryRepresentation')
        airflow_slice.Representation = 'Surface'
        airflow_slice.ColorArrayName = ['POINTS', 'U']
        airflow_slice.LookupTable = uLUT
        airflow_slice.SelectTCoordArray = 'None'
        airflow_slice.SelectNormalArray = 'None'
        airflow_slice.SelectTangentArray = 'None'
        airflow_slice.OSPRayScaleArray = 'U'
        airflow_slice.OSPRayScaleFunction = 'PiecewiseFunction'
        airflow_slice.SelectOrientationVectors = 'U'
        airflow_slice.ScaleFactor = 1.4000000000000001
        airflow_slice.SelectScaleArray = 'None'
        airflow_slice.GlyphType = 'Arrow'
        airflow_slice.GlyphTableIndexArray = 'None'
        airflow_slice.GaussianRadius = 0.07
        airflow_slice.SetScaleArray = ['POINTS', 'U']
        airflow_slice.ScaleTransferFunction = 'PiecewiseFunction'
        airflow_slice.OpacityArray = ['POINTS', 'U']
        airflow_slice.OpacityTransferFunction = 'PiecewiseFunction'
        airflow_slice.DataAxesGrid = 'GridAxesRepresentation'
        airflow_slice.PolarAxes = 'PolarAxesRepresentation'
        airflow_slice.SelectInputVectors = ['POINTS', 'U']
        airflow_slice.WriteLog = ''

        airflow_slice.ScaleTransferFunction.Points = [-1.3226988315582275, 0.0, 0.5, 0.0, 1.0460031032562256, 1.0, 0.5, 0.0]
        airflow_slice.OpacityTransferFunction.Points = [-1.3226988315582275, 0.0, 0.5, 0.0, 1.0460031032562256, 1.0, 0.5, 0.0]

        simple.Hide(foam_reader)
        
        uLUT.ApplyPreset('Turbo', True)
        animationScene.AnimationTime = float(self.state.simTime)

        airflow_slice.SetScalarBarVisibility(self.view, True)
        airflow_slice.RescaleTransferFunctionToDataRange(False, True)
        self.view.Update()

        self.view.MakeRenderWindowInteractor(True)
        self.ctrl.view_reset_camera()
        self.ctrl.view_update()
    
    def update_simProgress(self, delta):
        with self.state:
            self.state.simProgress += delta

    @asynchronous.task
    async def _async_simulate(self, **kwargs):
        self.simplefoam()
        self.update_simProgress(80)
        await asyncio.sleep(0.05)
        self.view_foam()
        self.update_simProgress(20)
        await asyncio.sleep(0.05)
        with self.state:
            self.state.sim_running = False
    
    def run_sim(self, **kwargs):
        if self.toSimulate:
            self.state.sim_running = True
            asynchronous.create_task(self._async_simulate())


    # Selection Change
    def actives_change(self, ids):
        _id = ids[0]
        if _id == "1":  # Set Environment
            self._server.state.active_ui = "environment"
        elif _id == "2":  # Simulate Airflow
            self._server.state.active_ui = "airflow"
        else:
            self._server.state.active_ui = "nothing"

    def pipeline_widget(self):
        trame.GitTree(
            sources=(
                "pipeline",
                [
                    {"id": "1", "parent": "0", "visible": 1, "name": "Set Environment"},
                    {"id": "2", "parent": "1", "visible": 1, "name": "Simulate Airflow"},
                ],
            ),
            actives_change=(self.actives_change, "[$event]"),
        )

    def ui_card(self, title, text, ui_name):
        with vuetify.VCard(v_show=f"active_ui == '{ui_name}'"):
            vuetify.VCardTitle(
                title,
                classes="grey lighten-1 py-1 grey--text text--darken-3",
                style="user-select: none; cursor: pointer",
                hide_details=True,
                dense=True,
            )
            vuetify.VCardText(
                text,
                classes="grey lighten-1 pb-2 grey--text text--darken-3",
                style="user-select: none; cursor: pointer",
                hide_details=True,
                dense=True,
            )
            content = vuetify.VCardText(classes="py-2")
        return content

    # Set UI for environment setting

    def environment_control_panel(self):
        with self.ui_card(title="Set Environment", \
                          text="Convert the uploaded STL file to a simulation-compatible \
                            file and set the boundaries and patches of simulation.", \
                            ui_name="environment"):
            vuetify.VCardSubtitle(
                "Upload your STL File"
            )
            vuetify.VFileInput(
                multiple=True,
                show_size=True,
                small_chips=True,
                v_model=("files", None),
                dense=True,
                hide_details=True,
                accept=".stl",
                __properties=["accept"],
                classes="mx-2"
            )  
            
            vuetify.VCardSubtitle(
                "Input the dimensions of the block that will limit the scope of simulation and \
                    select also the patches from which the natural airflow will come in and out. \
                    Note that the dimensions are measured from the center ground of the geometry \
                        found in the uploaded STL file."
            )
            vuetify.VTextField(
                label="Length",
                v_model=("myLength", self.DEFAULT_VALUE),
                hint="Input a positive number",
                suffix="meters",
                classes="mx-2"
            )
            vuetify.VTextField(
                label="Width",
                v_model=("myWidth", self.DEFAULT_VALUE),
                hint="Input a positive number",
                suffix="meters",
                classes="mx-2"
            )
            vuetify.VTextField(
                label="Height",
                v_model=("myHeight", self.DEFAULT_VALUE),
                hint="Input a positive number",
                suffix="meters",
                classes="mx-2"
            )
            with vuetify.VRow(classes="pt-1", dense=True):
                with vuetify.VCol(cols="6"):
                    vuetify.VSelect(
                    # Inlet
                        v_model=("inlet", self.Patch.front),
                        items=(
                            "patches",
                            [
                                {"text": "front", "value": 0},
                                {"text": "back", "value": 1},
                                {"text": "left", "value": 2},
                                {"text": "right", "value": 3},
                            ],
                        ),
                        label="inlet",
                        hide_details=True,
                        dense=True,
                        outlined=True,
                        classes="ms-2",
                    )
                with vuetify.VCol(cols="6"):
                    vuetify.VSelect(
                    # Outlet
                        v_model=("outlet", self.Patch.back),
                        items=(
                            "patches",
                            [
                                {"text": "front", "value": 0},
                                {"text": "back", "value": 1},
                                {"text": "left", "value": 2},
                                {"text": "right", "value": 3},
                            ],
                        ),
                        label="outlet",
                        hide_details=True,
                        dense=True,
                        outlined=True,
                        classes="me-2",
                    )
            with vuetify.VRow(classes="pt-1", align="center", dense=True):
                with vuetify.VCol(classes="text-center", cols="12"):
                    vuetify.VBtn(
                        "Set",
                        click=self.run_set,
                        disabled=("set_running", False),
                        variant="tonal",
                        classes="pa-3"
                    )
            vuetify.VDivider(classes="mt-3")
            vuetify.VProgressLinear(
                absolute=True,
                #bottom=True,
                color="teal",
                height="20",
                v_model=("setProgress", 0),
                classes="pa-2"
            )
            vuetify.VDivider(classes="mt-5")
            vuetify.VAlert(
                "The simulation will not run if there are invalid inputs, i.e., negative numbers and similar inlet and outlet.",
                type="warning",
                classes="ma-2"
            )
    
    def simulation_control_panel(self):
        with self.ui_card(title="Simulate Airflow", text="Set the wind speed", ui_name="airflow"):
            with vuetify.VRow(classes="pt-1", dense=True):
                with vuetify.VCol(cols="6"):
                    vuetify.VTextField(
                        label="Wind Speed",
                        v_model=("myWindSpeed", str(self.DEFAULT_VALUE)),
                        hint="Input a positive number",
                        suffix="m/s",
                        classes="ms-2"
                )
                with vuetify.VCol(cols="6"):
                    vuetify.VTextField(
                        label="at Height",
                        v_model=("myWindHeight", str(self.DEFAULT_VALUE)),
                        hint="Input a positive number",
                        suffix="meters",
                        classes="me-2"
                    )
            vuetify.VSelect(
                # Landscape
                v_model=("aeroRoughness", self.Landscape.open),
                items=(
                    "landscapes",
                    [
                        {"text": "open", "value": 0},
                        {"text": "negligible obstacles", "value": 1},
                        {"text": "minimal grass", "value": 2},
                        {"text": "occassional obstacles", "value": 3},
                        {"text": "scattered obstacles", "value": 4},
                        {"text": "large obstacles", "value": 5},
                        {"text": "homogeneous large obstacles", "value": 6},
                        {"text": "varying sizes of obstacles", "value": 7},
                    ],
                ),
                label="landscape",
                hide_details=True,
                dense=True,
                outlined=True,
                classes="ms-2",
            )
            vuetify.VTextField(
                label="Simulation Time",
                v_model=("mySimTime", str(self.DEFAULT_VALUE)),
                hint="Input a positive number",
                suffix="seconds",
                classes="ma-2"
                )
            with vuetify.VRow(classes="pt-1", align="center", dense=True):
                with vuetify.VCol(classes="text-center", cols="12"):
                    vuetify.VBtn(
                        "Simulate",
                        click=self.run_sim,
                        disabled=("sim_running", False),
                        variant="tonal",
                        classes="pa-3"
                    )
            vuetify.VDivider(classes="mt-3")
            vuetify.VProgressLinear(
                absolute=True,
                #bottom=True,
                color="teal",
                height="20",
                v_model=("simProgress", 0),
                classes="pa-2"
            )
            vuetify.VDivider(classes="mt-5")
            vuetify.VAlert(
                "The simulation will not run if there is no environment set and there are negative inputs.",
                type="warning",
                classes="ma-2"
            )

    def ui(self, *args, **kwargs):
        with SinglePageWithDrawerLayout(self._server) as layout:
            #layout.icon.click = self.ctrl.view_reset_camera
            layout.title.set_text("Ventilation Simulator")

            with layout.drawer as drawer:
                # drawer components
                drawer.width = 320
                self.pipeline_widget()
                vuetify.VDivider(classes="mb-2")
                self.environment_control_panel()
                self.simulation_control_panel()

            with layout.content:
                with vuetify.VContainer(
                    fluid=True,
                    classes="pa-0 fill-height",
                ):
                    html_view = paraview.VtkRemoteView(self.view)
                    self.ctrl.view_update = html_view.update
                    self.ctrl.view_reset_camera = html_view.reset_camera

                # Footer
                # layout.footer.hide()


def create_engine(server=None):
    # Get or create server
    if server is None:
        server = get_server()

    if isinstance(server, str):
        server = get_server(server)

    return Engine(server)