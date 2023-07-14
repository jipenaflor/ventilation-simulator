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
        state.change("slicePos")(self.set_slicePos)

        # Create temporary directory for uer simulation
        self.user = tempfile.TemporaryDirectory(dir='./')
        shutil.copytree('./simulation', self.user.name, dirs_exist_ok=True)
        self.USER_DIR = self.user.name

        # Initialize internal and state variables
        
        self.FILENAMES = []
        self.DEFAULT_VALUE = 5

        self.uploaded = False
        self.stl_readers = dict()
        self.length = 5
        self.width = 5
        self.height = 5
        self.inlet = ""
        self.outlet = ""
        self.toSet = False
        self.setSuccess = False

        self.windSpeed = 5
        self.windHeight = 5
        self.windDirection = ""
        self.aeroRoughness = ""
        self.simTime = 5
        self.toSimulate = False

        self.changeFile = False
        self.changeSim = False
        
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
            if self.uploaded:
                for reader in self.stl_readers:
                    simple.Delete(self.stl_readers[reader])
            if self.changeFile:
                simple.Delete(self.foam_reader)
            self.ctrl.view_update()
            self.stl_readers.clear()
            self.toSet = False
            self.state.set_running = True
            return
        
        save_path = os.path.join(self.USER_DIR, 'constant', 'triSurface')
        input_list = []

        for file in files:
            filename = file.get("name")
            input_list.append(filename)
            bytes = file.get("content")
            write_path = os.path.join(save_path, filename)
            with open(write_path, "wb") as fw:
                fw.write(bytes)
            fw.close()
        
        # remove files in the save_path that are not listed in the upload form
        file_diff = set(os.listdir(save_path)) - set(input_list)
        for file_ in file_diff:
            os.remove(os.path.join(save_path, file_))

        # assign readers to each stl in save_path
        self.FILENAMES = os.listdir(save_path)
        for i in self.FILENAMES:
            self.stl_readers["{0}".format(i.split('.')[0])] = simple.STLReader(FileNames=[os.path.join(save_path, i)])
        
        for reader in self.stl_readers:
            environment = simple.Show(self.stl_readers[reader], self.view, 'GeometryRepresentation')
            environment.Opacity = 0.4
        self.view.AxesGrid.Visibility = 1
        self.uploaded = True
        self.ctrl.view_update()

        self.state.set_running = False
        self.toSet = True

    def validate_number(self, myNumber):
        try:
            valid = float(myNumber)
            return (valid > 0)
        except:
            logger.info("User puts an invalid input")
    
    def set_length(self, myLength, **kwargs):
        isPositive = self.validate_number(myLength)
        if isPositive:
            self.length = float(myLength)
            self.state.set_running = False
            return
        self.state.set_running = True
    
    def set_width(self, myWidth, **kwargs):
        isPositive = self.validate_number(myWidth)
        if isPositive:
            self.width = float(myWidth)
            self.state.set_running = False
            return
        self.state.set_running = True
    
    def set_height(self, myHeight, **kwargs):
        isPositive = self.validate_number(myHeight)
        if isPositive:
            self.height = float(myHeight)
            self.state.set_running = False
            return
        self.state.set_running = True
    
    def validate_patch(self):
        if self.inlet == self.outlet:
            self.state.set_running = True
            return
        self.state.set_running = False

    def set_inlet(self, inlet, **kwargs):
        if inlet == self.Patch.front:
            self.inlet = "(0 1 5 4)"
            if self.outlet == "(0 4 7 3)":      #front-left
                self.windDirection = "(-1 -1 0)"
            elif self.outlet == "(0 4 7 3)":    #front-right
                self.windDirection = "(1 -1 0)"
            self.windDirection = "(0 -1 0)"     #front-back
        elif inlet == self.Patch.back:
            self.inlet = "(3 7 6 2)"
            if self.outlet == "(0 4 7 3)":      #back-left
                self.windDirection = "(-1 1 0)"
            elif self.outlet == "(0 4 7 3)":    #back-right
                self.windDirection = "(1 1 0)"
            self.windDirection = "(0 1 0)"      #back-front
        elif inlet == self.Patch.left:
            self.inlet = "(0 4 7 3)"
            if self.outlet == "(0 1 5 4)":      #left-front
                self.windDirection = "(-1 -1 0)"
            elif self.outlet == "(3 7 6 2)":    #left-back
                self.windDirection = "(-1 1 0)"
            self.windDirection = "(-1 0 0)"     #left-right
        elif inlet == self.Patch.right:
            self.inlet = "(1 2 6 5)"
            if self.outlet == "(0 1 5 4)":      #right-front
                self.windDirection = "(1 -1 0)"
            elif self.outlet == "(3 7 6 2)":    #right-back
                self.windDirection = "(1 1 0)"
            self.windDirection = "(1 0 0)"      #right-left
        self.validate_patch()

    def set_outlet(self, outlet, **kwargs):
        if outlet == self.Patch.front:
            self.outlet = "(0 1 5 4)"
        elif outlet == self.Patch.back:
            self.outlet = "(3 7 6 2)"
        elif outlet == self.Patch.left:
            self.outlet = "(0 4 7 3)"
        elif outlet == self.Patch.right:
            self.outlet= "(1 2 6 5)"
        self.validate_patch()

    def removeHistory(self):
        if os.path.exists(os.path.join(self.USER_DIR, '{0}'.format(self.simTime))):
            shutil.rmtree(os.path.join(self.USER_DIR, '{0}'.format(self.simTime)))
        
        processors = ['processor{0}'.format(i) for i in range(12)]

        if all([os.path.exists(proc) for proc in processors]):
            for proc in processors:
                if os.path.exists(os.path.join(self.USER_DIR, proc, '{0}'.format(self.simTime))):
                    shutil.rmtree(os.path.join(self.USER_DIR, proc, '{0}'.format(self.simTime)))
            
    def convert(self, **kwargs):
        conversion_template = os.path.join('simulation', 'system', 'surfaceFeaturesDict')
        conversion_path = os.path.join(self.USER_DIR, 'system', 'surfaceFeaturesDict')
        with open(conversion_template, "r", encoding="utf-8") as fr:
            line = fr.readlines()

        line_ = line[16:]
        del line[16:]

        for file in self.FILENAMES:
            line.append("\"{0}\"\n".format(file))
        
        line += line_

        with open(conversion_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)

        toEmesh = subprocess.Popen('surfaceFeatures', cwd=self.USER_DIR)
        toEmesh.wait()
        self.update_setProgress(2)
    
    def block(self, **kwargs):
        # Modify blockMesh
        x = self.length
        y = self.width
        z = self.height
        vertices = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), \
                    (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]

        block_template = os.path.join('simulation', 'system', 'blockMeshDict')
        block_path = os.path.join(self.USER_DIR, 'system', 'blockMeshDict')

        with open(block_template, "r", encoding="utf-8") as fr:
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
        coeffs = ["epsilon", "k", "nut", "p", "U"]
        for coeff in coeffs:
            coeff_template = os.path.join('simulation', '0', coeff)
            with open(coeff_template, "r", encoding="utf-8") as fr:
                line = fr.readlines()
            for file in self.FILENAMES:
                content = self.coeffContent(coeff, file)
                coeff_path = os.path.join(self.USER_DIR, '0', coeff)
        
                for i in content:
                    line.append(i)

                with open(coeff_path, "w", encoding="utf-8") as fw:
                    if file == self.FILENAMES[-1]:
                        line.append("}\n")
                    fw.writelines(line)


        toBlock = subprocess.Popen("blockMesh", cwd=self.USER_DIR)
        toBlock.wait()
        self.update_setProgress(15)

    def coeffContent(self, coeff, file):
        epsilon = ["    {0}\n".format(file.split('.')[0]), \
                "    {\n", "        type            epsilonWallFunction;\n", \
                "        Cmu             0.09;\n", "        kappa           0.4;\n", \
                "        E               9.8;\n", "        value           $internalField;\n", \
                "    }\n", "\n"]
        
        k = ["    {0}\n".format(file.split('.')[0]), \
            "    {\n", "        type            kqRWallFunction;\n", \
            "        value           uniform 0.0;\n", \
            "    }\n", "\n"]
        
        nut = ["    {0}\n".format(file.split('.')[0]), \
            "    {\n", "        type            nutkAtmRoughWallFunction;\n", \
            "        z0              $z0;\n", "        value           uniform 0.0;\n", \
            "    }\n", "\n"]

        p = ["    {0}\n".format(file.split('.')[0]), \
            "    {\n", "        type            zeroGradient;\n", \
            "    }\n", "\n"]
        
        U = ["    {0}\n".format(file.split('.')[0]), \
            "    {\n", "        type            noSlip;\n", \
            "    }\n", "\n"]
        

        if coeff == "epsilon":
            return epsilon
        elif coeff == "k":
            return k
        elif coeff == "nut":
            return nut
        elif coeff == "p":
            return p
        elif coeff == "U":
            return U
    
    def mesh(self, **kwargs):
        mesh_template = os.path.join('simulation', 'system', 'snappyHexMeshDict')
        mesh_path = os.path.join(self.USER_DIR, 'system', 'snappyHexMeshDict')

        with open(mesh_template, "r", encoding="utf-8") as fr:
            line = fr.readlines()
        
        a = line[30:81]
        b = line[81:96]
        c = line[96:]
        del line[30:]
        toModify = ["geometry", "features", "surfaces"]

        for part in toModify:
            for file in self.FILENAMES:
                content = self.snappyContent(file, part)
                line += content
            if part == toModify[0]:
                line += a
            elif part == toModify[1]:
                line += b
            else:
                line += c
        
        with open(mesh_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)
        
        # modify decomposeParDict
        decompose_path = os.path.join(self.USER_DIR, 'system', 'decomposeParDict.orig')
        with open(decompose_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()
        
        line[18] = "method          hierarchical;\n"

        with open(decompose_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)

        commands = [['decomposePar', '-force'], ['mpirun', '-np', '12', 'snappyHexMesh', '-parallel', '-overwrite'], ['reconstructParMesh', '-constant']]
        
        for cmd in commands:
            process = subprocess.Popen(cmd, cwd=self.USER_DIR)
            process.wait()
        self.update_setProgress(78)
    

    def snappyContent(self, file, toModify):
        geometry = ["    {0}\n".format(file.split('.')[0]), \
                    "    {\n", "        type triSurfaceMesh;\n", \
                    "        file \"{0}\";\n".format(file), \
                    "    }\n", "\n"]

        features = ["        {\n", "            file \"{0}.{1}\";\n".format(file.split('.')[0], "eMesh"), \
                    "            level 2;\n", "        }\n"]

        surfaces = ["        {0}\n".format(file.split('.')[0]), \
                    "        {\n", "            level (2 2);\n", \
                    "        }\n", "\n"]
        
        if toModify == "geometry":
            return geometry
        elif toModify == "features":
            return features
        elif toModify == "surfaces":
            return surfaces
        

    def view_environment(self, **kwargs):
        if self.setSuccess:
            simple.Delete(self.foam_reader)
            del self.foam_reader
            if self.changeSim:
                simple.Delete(self.slice)
                del self.slice
                self.changeSim = False
            self.ctrl.view_reset_camera()
            self.ctrl.view_update()

        for reader in self.stl_readers:
            simple.Hide(self.stl_readers[reader], self.view)

        toFoam = subprocess.Popen(['paraFoam', '-builtin', '-touch'], cwd=self.USER_DIR)
        toFoam.wait()

        foam_file = self.USER_DIR + ".foam"
        foam_path = os.path.join(self.USER_DIR, foam_file)
        self.foam_reader = simple.OpenFOAMReader(FileName=foam_path)
        environment = simple.Show(self.foam_reader, self.view)
        environment.Opacity = 0.25
        self.view.AxesGrid.Visibility = 1
        self.ctrl.view_reset_camera()
        self.ctrl.view_update()

        self.update_setProgress(5)
    
    def update_setProgress(self, delta):
        with self.state:
            self.state.setProgress += delta

    @asynchronous.task
    async def _async_set(self, **kwargs):
        self.convert()
        await asyncio.sleep(0.01)
        self.block()
        await asyncio.sleep(0.01)
        self.mesh()
        await asyncio.sleep(0.05)
        self.view_environment()
        await asyncio.sleep(0.01)
        self.changeFile = True
        self.setSuccess = True
        with self.state:
            self.state.set_running = False
            self.state.sim_running = False
    
    async def run_set(self, **kwargs):
        if self.toSet and not self.state.set_running:
            self.removeHistory()
            self.state.setProgress = 0
            await asyncio.sleep(0.01)
            self.state.set_running = True
            asynchronous.create_task(self._async_set())

    def set_windSpeed(self, myWindSpeed, **kwargs):
        isPositive = self.validate_number(myWindSpeed)
        if isPositive and self.setSuccess:
            self.windSpeed = float(myWindSpeed)
            self.state.sim_running = False
            return
        self.state.sim_running = True
    
    def set_windHeight(self, myWindHeight, **kwargs):
        isPositive = self.validate_number(myWindHeight)
        if isPositive and self.setSuccess:
            self.windHeight = float(myWindHeight)
            self.state.sim_running = False
            return
        self.state.sim_running = True

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
            self.simTime = float(mySimTime)
            self.state.sim_running = False
            return
        self.state.sim_running = True

    def simplefoam(self, **kwargs):
        # modify ABLConditions Dict
        v = str(self.windSpeed)
        h = str(self.windHeight)
        t = str(self.simTime)

        ABL_path = os.path.join(self.USER_DIR, '0', 'include', 'ABLConditions')
        with open(ABL_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()
        
        line[8] = "Uref                 " + v + ";\n"
        line[9] = "Zref                 " + h + ";\n"
        line[11] = "flowDir              " + self.windDirection + ";\n"
        line[12] = "z0                   uniform " + self.aeroRoughness + ";\n"

        with open(ABL_path, "w", encoding="utf-8") as fw:
            fw.writelines(line)
        
            # modify controlDict
        control_path = os.path.join(self.USER_DIR, 'system', 'controlDict')
        with open(control_path, "r", encoding="utf-8") as fr:
            line = fr.readlines()
        
        line[23] = "endTime         " + t + ";\n"
        line[29] = "writeInterval   " + t + ";\n"

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
                    ['reconstructPar'],]
        
        if self.changeSim:
            del commands[0]

        for cmd in commands:
            process = subprocess.Popen(cmd, cwd=self.USER_DIR)
            process.wait()
        self.update_simProgress(80)
    
    def view_foam(self, **kwargs):
        if self.state.postProcessing:
            simple.Delete(self.foam_reader)
            del self.foam_reader
            if self.changeSim:
                simple.Delete(self.slice)
                del self.slice
            self.ctrl.view_reset_camera()
            self.ctrl.view_update()

        for reader in self.stl_readers:
            environment = simple.Show(self.stl_readers[reader], self.view, 'GeometryRepresentation')
            environment.Opacity = 0.25
        
        toFoam = subprocess.Popen(['paraFoam', '-builtin', '-touch'], cwd=self.USER_DIR)
        toFoam.wait()

        foam_file = self.USER_DIR + ".foam"
        foam_path = os.path.join(self.USER_DIR, foam_file)

        self.foam_reader = simple.OpenFOAMReader(FileName=foam_path)
        self.foam_reader.MeshRegions = ['internalMesh']
        self.foam_reader.CellArrays = ['U']
        airflow = simple.Show(self.foam_reader, self.view, 'UnstructuredGridRepresentation')
        
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
        self.slice = simple.Slice(Input=self.foam_reader)
        self.slice.SliceType = 'Plane'
        self.slice.HyperTreeGridSlicer = 'Plane'
        self.slice.SliceOffsetValues = [0.0]
        self.slice.SliceType.Origin = [0.0, 0.0, 1.0]
        self.slice.SliceType.Normal = [0.0, 0.0, 1.0]

        airflow_slice = simple.Show(self.slice, self.view, 'GeometryRepresentation')
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

        simple.Hide(self.foam_reader)
        
        uLUT.ApplyPreset('Turbo', True)
        animationScene.AnimationTime = float(self.simTime)

        airflow_slice.SetScalarBarVisibility(self.view, True)
        airflow_slice.RescaleTransferFunctionToDataRange(False, True)
        self.view.Update()

        self.view.MakeRenderWindowInteractor(True)
        self.ctrl.view_reset_camera()
        self.ctrl.view_update()
        
        self.changeSim = True
        self.update_simProgress(15)
    
    def update_simProgress(self, delta):
        with self.state:
            self.state.simProgress += delta

    @asynchronous.task
    async def _async_simulate(self, **kwargs):
        self.simplefoam()
        await asyncio.sleep(0.05)
        self.view_foam()
        await asyncio.sleep(0.05)
        with self.state:
            self.state.postProcessing = False
            self.state.sim_running = False
    
    async def run_sim(self, **kwargs):
        if not self.state.sim_running:
            self.removeHistory()
            self.state.simProgress = 0
            await asyncio.sleep(0.01)
            self.state.sim_running = True
            self.state.postProcessing = True
            self.update_simProgress(5)
            await asyncio.sleep(0.01)
            asynchronous.create_task(self._async_simulate())

    def set_slicePos(self, slicePos, **kwargs):
        if self.state.postProcessing == True:
            return
        else:
            self.slice.SliceType.Origin = [0.0, 0.0, float(slicePos)]
            self.ctrl.view_update()
        
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
                          text="Convert the uploaded STL files to a simulation-compatible \
                            files and set the boundaries and patches of simulation.", \
                            ui_name="environment"):
            vuetify.VCardSubtitle(
                "Upload your Binary STL Files"
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
                classes="ma-2"
            )
            vuetify.VCardSubtitle(
                "Input the dimensions of the block that delimits the scope of simulation and \
                    select also the patches from which the natural airflow will come in and out. \
                    Note that the dimensions are measured from the center ground of the geometry \
                        found in the uploaded STL files."
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
                        disabled=("set_running", True),
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
        with self.ui_card(title="Simulate Airflow", \
                          text="Set the parameters for simulation of natural airflow", \
                            ui_name="airflow"):
            with vuetify.VRow(classes="pt-1", dense=True):
                with vuetify.VCol(cols="6"):
                    vuetify.VTextField(
                        label="Wind Speed",
                        v_model=("myWindSpeed", self.DEFAULT_VALUE),
                        hint="Input a positive number",
                        suffix="m/s",
                        classes="ms-2"
                )
                with vuetify.VCol(cols="6"):
                    vuetify.VTextField(
                        label="at Height",
                        v_model=("myWindHeight", self.DEFAULT_VALUE),
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
                classes="ma-2",
            )
            vuetify.VTextField(
                label="Simulation Time",
                v_model=("mySimTime", self.DEFAULT_VALUE),
                hint="Input a positive number",
                suffix="seconds",
                classes="ma-2"
                )
            with vuetify.VRow(classes="pt-1", align="center", dense=True):
                with vuetify.VCol(classes="text-center", cols="12"):
                    vuetify.VBtn(
                        "Simulate",
                        click=self.run_sim,
                        disabled=("sim_running", True),
                        variant="tonal",
                        classes="mb-2"
                    )
            vuetify.VDivider(classes="mt-3")
            vuetify.VProgressLinear(
                absolute=True,
                color="teal",
                height="20",
                v_model=("simProgress", 0),
                classes="pa-2"
            )
            vuetify.VDivider(classes="mt-5")
            vuetify.VCardSubtitle("Adjust the filter position")
            vuetify.VSlider(
                    label="Height [m]",
                    v_model=("slicePos", 1),
                    min=0.1, max=10, step=0.2,
                    dense=True, hide_details=True,
                    thumb_label=True,
                    disabled=("postProcessing", True),
                    classes = "pa-2"
                )
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