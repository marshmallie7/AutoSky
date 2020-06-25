import os.path
import json
import PyVMF.PyVMF as PyVMF
import builtinmodelreplace
from PyVMF.exceptions import *
from exceptions import *
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
import time
import threading
import traceback

#The application itself
class AutoSky(ttk.Frame):
	def __init__(self, *args, **kwargs):
		self.parent = tk.Tk()
		self.parent.title("AutoSky")
		self.icon = tk.PhotoImage(file=os.path.join(os.path.dirname(os.path.realpath(__file__)),"resources","icon.png"))
		self.parent.iconphoto(True,self.icon)
		self.parent.resizable(False,False)
		self.parent.protocol("WM_DELETE_WINDOW",self.close)
		super().__init__(self.parent, *args, **kwargs)

		#Init default config dictionary and override defaults with the settings specified with config.json, if it exists. (Any settings not specified within config.json will remain default).
		self.config = {"inputPath":"",
						"outputPath":"",
						"skyboxOnly":False,
						"replaceModels":True,
						"copyFogSettings":True}
		p = os.path.join(os.path.dirname(os.path.realpath(__file__)),"config.json")
		if os.path.exists(p):
			with open(p,"r") as f:
				for key, val in json.load(f).items():
					self.config[key] = val
		else: #Write default config if no json exists
			self.writeConfig()

		#Init built-in modelreplace dictionary
		self.builtinmodelreplace = builtinmodelreplace.dic

		#Init user modelreplace dictionary by loading up all keyvals specified in modelreplace.json, if it exists; else, init an empty dictionary.
		p = os.path.join(os.path.dirname(os.path.realpath(__file__)),"modelreplace.json")
		if os.path.exists(p):
			with open(p,"r") as f:
				self.usermodelreplace = json.load(f)
		else:
			self.usermodelreplace = {}
			self.writeUserModelreplace()

		#For this session, override any models in built-in modelreplace that are specified in user modelreplace
		remove = []
		for model in self.usermodelreplace:
			if model in self.builtinmodelreplace:
				remove.append(model)
		for model in remove:
			del self.builtinmodelreplace[model]

		#Init full modelreplace dictionary
		self.modelreplace = {**self.builtinmodelreplace,**self.usermodelreplace}

		#Instantiate the notebook and both its tabs (Files, Options)
		self.notebook = ttk.Notebook(self)
		self.notebook.parent = self
		self.filesTab = FilesTab(self.notebook)
		self.notebook.add(self.filesTab,text="Files")
		self.optionsTab = OptionsTab(self.notebook)
		self.notebook.add(self.optionsTab,text="Options")
		self.notebook.select(self.filesTab)
		self.notebook.enable_traversal()

		#Instantiate the "run bar" which is always present regardless of tab, containing the progress bar and run button
		self.runBar = RunBar(self)

		#Vars for keeping track of the skybox generation start time
		self.startTime = 0

		#Initialize all GUI elements to their config-specified settings
		self.filesTab.setInputPath(self.config["inputPath"])
		self.filesTab.setOutputPath(self.config["outputPath"])
		self.optionsTab.setWhetherSkyboxOnly(self.config["skyboxOnly"])
		self.optionsTab.setIfUseModelReplace(self.config["replaceModels"])
		self.optionsTab.setWhetherCopyFogSettings(self.config["copyFogSettings"])

	def run(self):
		self.writeAll()
		thread = threading.Thread(target=self.generate,args=(self.config["inputPath"],self.config["outputPath"]),
																kwargs={"skyboxOnly":self.config["skyboxOnly"],
																		"replaceModels":self.config["replaceModels"],
																		"copyFogSettings":self.config["copyFogSettings"]},
																daemon=True)
		self.startTime = time.time()
		self.runBar.run()
		thread.start()

	def generate(self,inputPath,outputPath,skyboxOnly=True,replaceModels=True,copyFogSettings=True,debugMode=True):
		parseError = False
		try:
			if outputPath[-4:] != ".vmf":
				self.finishWithError("Invalid output path, or output path is not a VMF.")
				return
			if inputPath[-4:] == ".vmf":
				try:
					inputVMF = PyVMF.load_vmf(inputPath)
				except FileNotFoundError:
					self.finishWithError(f"{inputPath} is not a valid filepath")
					return
				except Exception:
					self.finishWithError("An error occurred parsing {}:\n\n".format(os.path.basename(inputPath)) + traceback.format_exc() + "\nIf you're sure your VMF isn't corrupt or improperly formatted, please report this issue on the AutoSky GitHub with as much information as possible!")
					print(traceback.format_exc())
					return
			else:
				self.finishWithError("Invalid input path, or input path is not a VMF.")
				return
			if inputPath == outputPath:
				self.finishWithError("Overwriting the input VMF is currently prohibited, as AutoSky is in beta. Please enter a different output path.")
				return

			outputVMF = PyVMF.new_vmf()
			outputVMF.versioninfo.editorbuild = inputVMF.versioninfo.editorbuild

			#Copy all solids and prop_statics from AutoSky visgroup into exportVmf
			items = inputVMF.get_all_from_visgroup("AutoSky",True,not skyboxOnly)
			if len(items) == 0:
				yes = self.yesNoQuestion("Continue?","No AutoSky visgroup was found, or if it exists it doesn't contain anything. Proceed with generating an empty skybox?")
				if not yes:
					self.finishWithError()
					return
			for item in items:
				item.editor.remove_all_visgroups()
				item.editor.remove_all_groups()
				item.editor.visgroupshown = 1
				if isinstance(item,PyVMF.Solid):
					outputVMF.add_solids(item)
				else:
					outputVMF.add_entities(item)

			#Scale contents of outputVmf by a factor of 1/16, relative to the origin, and replace its prop_statics' models (if replaceModels=True)
			scaler = 1/16
			mapOrigin = PyVMF.Vertex(0,0,0)
			neato = outputVMF.get_solids_and_entities()
			for item in outputVMF.get_solids_and_entities(True):
				item.scale(mapOrigin,scaler,scaler,scaler)
				if replaceModels and isinstance(item,(PyVMF.PropStatic,PyVMF.PropDynamic)):
					if item.model in self.modelreplace:  #If the prop's model is in the modelreplace dictionary
						item.model = self.modelreplace[item.model] #Set that prop's model to the replacement specified in the dictionary
					else:
						yes = self.yesNoQuestion("Unidentified model",f"The model {item.model} was found in the AutoSky visgroup, but no replacement is specified in the model replacement index. Proceed without replacing it?")
						if not yes:
							self.finishWithError()
							return
					#This is the only stock skybox prop in TF2 that has a different orientation from the normal scale prop, as far as I know, so we have to rotate it. Thanks Valve
					if item.model == "models/props_foliage/tree_pine01_4cluster_skybox.mdl":
						item.angles += PyVMF.Vertex(0,-90,0)

			#Generate sky camera at origin
			cam = PyVMF.EntityGenerator.sky_camera(mapOrigin)
			outputVMF.add_entities(cam)

			if copyFogSettings:
				controller = None
				for entity in inputVMF.get_entities(True):
					if isinstance(entity,PyVMF.EnvFogController):
						controller = entity
						cam.fogcolor = controller.fogcolor
						cam.fogcolor2 = controller.fogcolor2
						cam.fogdir = controller.fogdir
						cam.fogend = controller.fogend
						cam.fogmaxdensity = controller.fogmaxdensity
						cam.fogstart = controller.fogstart
						cam.fogblend = controller.fogblend
						cam.fogenable = controller.fogenable
						cam.use_angles = controller.use_angles
						break

			#Determine bounds of skybox room
			xLowerBound = outputVMF.getXExtremity(False)
			xUpperBound = outputVMF.getXExtremity(True)

			yLowerBound = outputVMF.getYExtremity(False)
			yUpperBound = outputVMF.getYExtremity(True)

			zLowerBound = outputVMF.getZExtremity(False)
			zUpperBound = outputVMF.getZExtremity(True)

			#if debugMode:
			#	print("X extremities:",xLowerBound,xUpperBound)
			#	print("Y extremities:",yLowerBound,yUpperBound)
			#	print("Z extremities:",zLowerBound,zUpperBound)

			minBlockUnit = 128
			gridSnap = 64
			wallThickness = 16

			numBlocksTowardXLowerBound = abs(xLowerBound // minBlockUnit) + 1
			numBlocksTowardXUpperBound = abs(xUpperBound // minBlockUnit) + 1
			totalXHammerUnits = (numBlocksTowardXLowerBound + numBlocksTowardXUpperBound) * minBlockUnit

			numBlocksTowardYLowerBound = abs(yLowerBound // minBlockUnit) + 1
			numBlocksTowardYUpperBound = abs(yUpperBound // minBlockUnit) + 1
			totalYHammerUnits = (numBlocksTowardYLowerBound + numBlocksTowardYUpperBound) * minBlockUnit

			numBlocksTowardZLowerBound = abs(zLowerBound // minBlockUnit) + 1
			numBlocksTowardZUpperBound = abs(zUpperBound // minBlockUnit) + 1
			totalZHammerUnits = (numBlocksTowardZLowerBound + numBlocksTowardZUpperBound) * minBlockUnit

			room = PyVMF.SolidGenerator.room(mapOrigin,totalXHammerUnits,totalYHammerUnits,totalZHammerUnits,wallThickness)

			#Determine number of x units to move to fix room's x position. Positive if needs to move upward, negative if needs to move downward
			numBlocksToMoveX = (numBlocksTowardXUpperBound - numBlocksTowardXLowerBound) / 2

			#Determine number of y units to move to fix room's x position. Positive if needs to move upward, negative if needs to move downward
			numBlocksToMoveY = (numBlocksTowardYUpperBound - numBlocksTowardYLowerBound) / 2

			#Determine number of z units to move to fix room's x position. Positive if needs to move upward, negative if needs to move downward
			numBlocksToMoveZ = (numBlocksTowardZUpperBound - numBlocksTowardZLowerBound) / 2

			for wall in room:
				wall.set_texture("tools/toolsskybox")
				wall.move(numBlocksToMoveX*minBlockUnit,numBlocksToMoveY*minBlockUnit,numBlocksToMoveZ*minBlockUnit)
			outputVMF.add_solids(*room)

			if not skyboxOnly:
				#Clear the old skybox from input VMF (anything within its "3D Skybox (AutoSky)" visgroup)
				inputVMF.delete_visgroup_contents("3D Skybox (AutoSky)")

				#Relocate the new skybox to 192 units below the lowest coordinate in the input VMF (while snapping to 64x64 grid)
				skyboxCurrentTopZ = outputVMF.getZExtremity(True) - wallThickness
				skyboxRelocatedTopZ = inputVMF.getZExtremity(False) - (inputVMF.getZExtremity(False) % gridSnap) - 192
				for item in outputVMF.get_solids_and_entities():
					item.move(0,0,skyboxRelocatedTopZ-skyboxCurrentTopZ)

				#Copy the new skybox over from outputVMF to inputVMF, and add it to the special "3D Skybox (AutoSky)" visgroup
				skyboxSolids = outputVMF.get_solids(False,False) #TODO test getting both entities/solids at same time e.g. get_solids_and_entities
				skyboxEntities = outputVMF.get_entities(False,True)
				inputVMF.add_solids(*skyboxSolids)
				inputVMF.add_entities(*skyboxEntities)
				allSkyboxElements = skyboxSolids + skyboxEntities
				inputVMF.add_to_visgroup("3D Skybox (AutoSky)",*allSkyboxElements)
				
				outputVMF = inputVMF
			
			try:
				outputVMF.export(outputPath)
			except FileNotFoundError:
				self.finishWithError(f"{os.path.dirname(outputPath)}/ is not a valid directory")
				return

		except:
			self.finishWithError("An unexpected error occurred while generating the skybox:\n\n" + traceback.format_exc() + "\nPlease report this issue on the AutoSky GitHub with as much information as possible!")
			print(traceback.format_exc())
			return

		self.finish()

	def finish(self):
		self.runBar.finish("Done! ({:.2f} seconds)".format(time.time() - self.startTime))

	def finishWithError(self,message=None):
		self.runBar.finish("Waiting...")
		if message is not None:
			messagebox.showerror("Error",message)

	def yesNoQuestion(self,title,message):
		return messagebox.askyesno(title,message)

	def mainloop(self):
		self.parent.mainloop()

	def updateConfig(self,key,val):
		self.config[key] = val

	def addToModelreplace(self,model,skyboxModel):
		self.usermodelreplace[model] = skyboxModel
		self.modelreplace[model] = skyboxModel

	def removeFromModelreplace(self,model):
		self.usermodelreplace.pop(model,None)
		self.modelreplace.pop(model,None)

	def getModelreplaceLength(self):
		return len(self.modelreplace)

	def writeConfig(self):
		p = os.path.join(os.path.dirname(os.path.realpath(__file__)),"config.json")
		with open(p,"w") as f:
			json.dump(self.config,f,indent=4)
	
	def writeUserModelreplace(self):
		p = os.path.join(os.path.dirname(os.path.realpath(__file__)),"modelreplace.json")
		with open(p,"w") as f:
			json.dump(self.usermodelreplace,f,indent=4)
	
	def writeAll(self):
		self.writeConfig()
		self.writeUserModelreplace()

	def close(self,*args):
		self.writeAll()
		self.parent.destroy()

	def align(self):
		self.parent.update_idletasks()
		width = self.parent.winfo_width()
		height = self.parent.winfo_height()
		x = (self.parent.winfo_screenwidth() // 2) - (width // 2)
		y = (self.parent.winfo_screenheight() // 2) - (height // 2)
		self.parent.geometry('{}x{}+{}+{}'.format(width, height, 128, 128))

	def grid(self, **kwargs):
		super().grid(**kwargs)
		self.notebook.grid(row=0,column=0,columnspan=3)
		self.filesTab.gridChildren()
		self.optionsTab.gridChildren()
		self.runBar.grid(row=1,column=0)

class FilesTab(ttk.Frame):
	def __init__(self, parent, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)
		self.parent = parent

		self.inputLabel = Label(self,text="Input VMF:")
		self.inputEntry = EntryWithDefaultText(self,width=80,configDictAndKeyToUpdate=(self.parent.parent.config,"inputPath"))
		self.chooseVMFButton = VMFSearchButton(self,text="Browse...",entry=self.inputEntry)

		self.outputLabel = Label(self,text="Output as:")
		self.outputEntry = EntryWithDefaultText(self,width=80,configDictAndKeyToUpdate=(self.parent.parent.config,"outputPath")) #Keep an eye on the config var name; it might be being used by ttk.frame as a method already?
		self.saveVMFButton = VMFSaveButton(self,text="Browse...",entry=self.outputEntry)

	def getInputPath(self):
		return self.inputEntry.getText()

	def setInputPath(self,path):
		self.inputEntry.setText(path)

	def getOutputPath(self):
		return self.outputEntry.getText()

	def setOutputPath(self,path):
		self.outputEntry.setText(path)

	def gridChildren(self):
		self.inputLabel.grid(row=0,column=0,padx=4,pady=(12,2))
		self.inputEntry.grid(row=0,column=1,padx=4,pady=(12,2))
		self.chooseVMFButton.grid(row=0,column=2,padx=4,pady=(12,2))
		self.outputLabel.grid(row=1,column=0,padx=4,pady=8)
		self.outputEntry.grid(row=1,column=1,padx=4,pady=8)
		self.saveVMFButton.grid(row=1,column=2,padx=4,pady=8)

class OptionsTab(ttk.Frame):
	def __init__(self, parent, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)
		self.parent = parent

		self.chooseOutputTypeBar = ttk.Frame(self)
		self.chooseOutputTypeLabel = Label(self.chooseOutputTypeBar,text="Output type:")
		self.chooseOutputTypeRadiobuttonVariable = tk.IntVar()
		self.chooseOutputTypeRadiobuttonVariable.trace("w",self.updateConfigOutputSkyboxOnly)
		self.chooseOutputTypeRadiobuttonA = ttk.Radiobutton(self.chooseOutputTypeBar,
															text="3D skybox only",
															variable=self.chooseOutputTypeRadiobuttonVariable,
															value=0)
		self.chooseOutputTypeRadiobuttonB = ttk.Radiobutton(self.chooseOutputTypeBar,
															text="Input VMF with 3D skybox copied in",
															variable=self.chooseOutputTypeRadiobuttonVariable,
															value=1)

		self.chooseIfUsingModelReplaceBar = ttk.Frame(self)
		self.modelReplaceCheckbutton = Checkbutton(self.chooseIfUsingModelReplaceBar,text="Use the model replacement index to replace prop models with their 3D skybox versions",configDictAndKeyToUpdate=(self.parent.parent.config,"replaceModels"))
		self.modelReplaceMenuOpenButton = ttk.Button(self.chooseIfUsingModelReplaceBar,text="Model replacement index",command=self.openModelReplaceMenu)
													#TODO: add model replacement index and link to it via this button

		self.chooseIfShouldCopyFogSettingsBar = ttk.Frame(self)
		self.copyFogSettingsCheckbutton = Checkbutton(self.chooseIfShouldCopyFogSettingsBar,text="If the input VMF has an env_fogcontroller, copy all its fog settings to the output skybox's sky_camera",configDictAndKeyToUpdate=(self.parent.parent.config,"copyFogSettings"))

		self.modelReplaceMenu = None

	def openModelReplaceMenu(self, *args):
		if self.modelReplaceMenu is None:
			self.modelReplaceMenu = ModelReplaceMenu(self)
			self.modelReplaceMenu.grid(row=0,column=0,sticky="nswe")
			self.modelReplaceMenu.align()
		else:
			self.modelReplaceMenu.lift()

	def outputSkyboxOnly(self):
		return bool(self.chooseOutputTypeRadiobuttonVariable.get())

	def setWhetherSkyboxOnly(self,_bool):
		self.chooseOutputTypeRadiobuttonVariable.set(int(not _bool))

	def useModelReplace(self):
		return self.modelReplaceCheckbutton.isChecked()

	def setIfUseModelReplace(self,_bool):
		self.modelReplaceCheckbutton.setChecked(_bool)

	def copyFogSettings(self):
		return self.copyFogSettingsCheckbutton.isChecked()

	def setWhetherCopyFogSettings(self,_bool):
		self.copyFogSettingsCheckbutton.setChecked(_bool)

	def updateConfigOutputSkyboxOnly(self,*args):
		self.parent.parent.config["skyboxOnly"] = not bool(self.chooseOutputTypeRadiobuttonVariable.get())

	def gridChildren(self):
		self.chooseOutputTypeBar.grid(row=0,column=0,sticky="w")
		self.chooseOutputTypeLabel.grid(row=0,column=0,padx=4,pady=(6,0))
		self.chooseOutputTypeRadiobuttonA.grid(row=0,column=1,padx=4,pady=(6,0))
		self.chooseOutputTypeRadiobuttonB.grid(row=0,column=2,padx=4,pady=(6,0))

		self.chooseIfUsingModelReplaceBar.grid(row=1,column=0,sticky="w")
		self.modelReplaceCheckbutton.grid(row=1,column=0,padx=4,pady=2)
		self.modelReplaceMenuOpenButton.grid(row=1,column=1,padx=2,pady=2)

		self.chooseIfShouldCopyFogSettingsBar.grid(row=2,column=0,sticky="w")
		self.copyFogSettingsCheckbutton.grid(row=2,column=0,padx=4,pady=(0,6))

class ModelReplaceMenu(tk.Toplevel):
	def __init__(self, parent, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)
		self.parent = parent
		self.title("Model replacement index")
		self["height"] = 256
		self["width"] = 512
		self.minsize(645,320)

		self.customreplacementmarker = tk.PhotoImage(file=os.path.join(os.path.dirname(os.path.realpath(__file__)),"resources","customreplacementmarker.png"))

		self.mainframe = ttk.Frame(self,padding=(8,8,8,8))
		self.topframe = ttk.Frame(self.mainframe)
		self.toplabel = Label(self.topframe,wraplength=640,text='If "Use the model replacement index" is checked, prop_statics/dynamics with a model found within the first column will be replaced with the skybox model specified in the second.')
		self.topsublabel_img = Label(self.topframe,image=self.customreplacementmarker)
		self.topsublabel = Label(self.topframe,text="indicates custom-specified replacements")

		self.middleframe = ttk.Frame(self.mainframe)

		self.tree = ttk.Treeview(self.middleframe)
		self.tree["columns"] = ("#1")

		self.tree.column("#0",width=300)
		self.tree.column("#1",width=300)

		self.tree.heading("#0",text="Model")
		self.tree.heading("#1",text="Skybox model")

		self.scrollBar = ttk.Scrollbar(self.middleframe)
		self.scrollBar.configure(command=self.tree.yview)
		self.tree.configure(yscrollcommand=self.scrollBar.set)

		#self.tree.bind("<Double-1>",self.openEditWindow)

		self.bottomframe = ttk.Frame(self.mainframe)
		self.addButton = ttk.Button(self.bottomframe,text="Add custom replacements",command=self.openAddWindow)
		self.removeButton = ttk.Button(self.bottomframe,text="Remove selected",command=self.removeSelectedFromModelreplace)

		self.addModelWindow = None
		#self.editModelWindow = None

		self.protocol("WM_DELETE_WINDOW",self.close)

		for model, skyboxModel in parent.parent.parent.builtinmodelreplace.items():
			self.tree.insert("",0,text=model,values=(skyboxModel))
		for model, skyboxModel in parent.parent.parent.usermodelreplace.items():
			self.tree.insert("", 0, text=model, values=(skyboxModel),image=self.customreplacementmarker)


	def grid(self,**kwargs):
		self.mainframe.grid(row=0,column=0,sticky="nswe")
		self.topframe.grid(row=0,column=0)
		self.toplabel.grid(row=0,column=0)
		self.topsublabel_img.grid(row=1,column=0,sticky="w")
		self.topsublabel.grid(row=1,column=0,sticky='w',padx=(20,0))
		self.middleframe.grid(row=1,column=0,sticky="nswe")
		self.tree.grid(row=0,column=0,pady=8,sticky="nswe")
		self.scrollBar.grid(row=0,column=1,sticky="nswe")
		self.bottomframe.grid(row=2,column=0)
		self.addButton.grid(row=0,column=0)
		self.removeButton.grid(row=0,column=1)

		self.columnconfigure(0,weight=1)
		self.mainframe.columnconfigure(0,weight=1)
		self.topframe.columnconfigure(0,weight=1)
		self.middleframe.columnconfigure(0, weight=1)

		self.rowconfigure(0, weight=1)
		self.mainframe.rowconfigure(1,weight=1)
		self.middleframe.rowconfigure(0,weight=1)

	def openAddWindow(self,*args):
		if self.addModelWindow is None:
			self.addModelWindow = AddModelWindow(self)
			self.addModelWindow.grid(row=0,column=0)
			self.addModelWindow.align()
		else:
			self.addModelWindow.lift()

	def close(self,*args):
		if self.addModelWindow is not None:
			self.addModelWindow.destroy()
		self.parent.modelReplaceMenu = None
		self.destroy()

	def align(self):
		self.update_idletasks()
		width = self.winfo_width()
		height = self.winfo_height()
		self.geometry('{}x{}+{}+{}'.format(width, height, self.parent.parent.parent.parent.winfo_x() + 32, self.parent.parent.parent.parent.winfo_y() + 32))

	def addToModelreplace(self,model,skyboxModel):
		self.tree.insert("",0,text=model,values=(skyboxModel),image=self.customreplacementmarker)
		self.parent.parent.parent.addToModelreplace(model,skyboxModel)

	def removeSelectedFromModelreplace(self,*args):
		models = []
		cancel = False
		for model in self.tree.selection():
			d = self.tree.item(model)
			if d["text"] in self.parent.parent.parent.builtinmodelreplace:
				cancel = True
				messagebox.showerror("Error", "One or more of the selected model(s) is in the built-in replacement index and can't be deleted.", parent=self)
				break
			else:
				models.append(model)
		if not cancel:
			for model in models:
				d = self.tree.item(model)
				del self.parent.parent.parent.modelreplace[d["text"]]
				del self.parent.parent.parent.usermodelreplace[d["text"]]
			self.tree.delete(*models)
			
	"""
	def openEditWindow(self,*args):
		if self.editModelWindow is None:
			selection = self.tree.item(self.tree.selection()[0])
			self.editModelWindow = EditModelWindow(self,selection["text"],selection["values"][0])
			self.editModelWindow.grid(row=0,column=0)
	"""

class AddModelWindow(tk.Toplevel):
	def __init__(self, parent, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)
		self.parent = parent
		self.title("Add custom replacements")
		self["height"] = 256
		self["width"] = 512
		self.resizable(False,False)
		self.mainframe = ttk.Frame(self,padding=(8,8,8,8))
		self.modelLabel = Label(self.mainframe,text='Model:')
		self.modelEntry = EntryWithDefaultText(self.mainframe,width=80,text="models/props_mining/rock003.mdl")
		self.replaceLabel = Label(self.mainframe,text='Skybox model to replace with:')
		self.replaceEntry = EntryWithDefaultText(self.mainframe,width=80,text="models/props_mining/rock003_skybox.mdl")
		self.addButton = ttk.Button(self.mainframe,text="Add",command=self.pressAdd,width=13)

		self.protocol("WM_DELETE_WINDOW",self.close)

	def pressAdd(self,*args):
		if (self.modelEntry.getText() == "") or (self.replaceEntry.getText() == ""):
			messagebox.showerror("Error","Please enter a model for both fields",parent=self)
		elif self.modelEntry.getText() in self.parent.parent.parent.parent.modelreplace:
			messagebox.showerror("Error",f"{self.modelEntry.getText()} is already in the replacement list",parent=self)
		else:
			self.parent.addToModelreplace(self.modelEntry.getText(),self.replaceEntry.getText())
			self.addButton["text"] = "Model added!"
			self.after(1000,self.resetAddButtonText)

	def resetAddButtonText(self,*args):
		self.addButton["text"] = "Add"

	def close(self,*args):
		self.parent.addModelWindow = None
		self.destroy()

	def align(self):
		self.update_idletasks()
		width = self.winfo_width()
		height = self.winfo_height()
		self.geometry('{}x{}+{}+{}'.format(width, height, self.parent.winfo_x() + 32, self.parent.winfo_y() + 32))

	def grid(self,**kwargs):
		self.mainframe.grid(row=0,column=0)
		self.modelLabel.grid(row=0,column=0,padx=(0,2))
		self.modelEntry.grid(row=0,column=1)
		self.replaceLabel.grid(row=1,column=0,padx=(0,2),pady=(4,0))
		self.replaceEntry.grid(row=1,column=1,pady=(4,0))
		self.addButton.grid(row=2,column=1,pady=(4,0),sticky="E")

#The "run bar" that contains the progress bar and run button. Always present regardless of current Notebook tab
class RunBar(ttk.Frame):
	def __init__(self, parent, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)
		self.parent = parent

		self.progressBar = ttk.Progressbar(self,mode="determinate",orient="horizontal",length=224)
		self.progressLabel = Label(self,text="Waiting...")
		self.runButton = ttk.Button(self,text="Generate",command=self.clickRunButton)

	def clickRunButton(self, *args):
		self.parent.run() #Call run on the application itself

	def run(self):
		self.progressLabel.setText("Working...")
		self.runButton["state"] = "disabled"
		self.progressBar.start(20)

	def finish(self,finishText): #time = how long (in seconds) the program took to execute
		self.progressLabel.setText(finishText)
		self.runButton["state"] = "normal"
		self.progressBar.stop()
		self.progressBar["value"] = 0

	def grid(self, **kwargs):
		super().grid(**kwargs)
		self.progressBar.grid(row=0,column=0,sticky="w",padx=2,pady=(7,0))
		self.progressLabel.grid(row=0,column=1,sticky="w",padx=2,pady=(7,0),columnspan=2)
		self.runButton.grid(row=0,column=2,sticky="e",padx=(344,0),pady=(7,0))

#Checkbutton class that handles its own activation variable (so don't supply it an activation variable in the constructor)
class Checkbutton(ttk.Checkbutton):
	def __init__(self, parent, *args, **kwargs):
		self.variable = tk.IntVar()
		kwargs["variable"] = self.variable

		if "configDictAndKeyToUpdate" in kwargs: #If "configDictAndKeyToUpdate" is provided, the provided config dict will be updated at the provided key to match the entry's current text string whenever the entry's text is modified.
			self.configDictToUpdate = kwargs["configDictAndKeyToUpdate"][0]
			self.configDictKeyToUpdate = kwargs["configDictAndKeyToUpdate"][1]
			self.variable.trace("w",self.updateConfigDict)
			del kwargs["configDictAndKeyToUpdate"]

		super().__init__(parent, *args, **kwargs)
		self.parent = parent

	def isChecked(self):
		return bool(self.variable.get())

	def setChecked(self,_bool):
		self.variable.set(int(_bool))

	def updateConfigDict(self,*args):
		self.configDictToUpdate[self.configDictKeyToUpdate] = self.isChecked()

#Label class that handles its own text variable (so don't supply it a textvariable in the constructor)
class Label(ttk.Label):
	def __init__(self, parent, *args, **kwargs):
		self.textvariable = tk.StringVar()
		if "text" in kwargs:
			self.textvariable.set(kwargs["text"])
		else:
			self.textvariable.set("")
		kwargs["textvariable"] = self.textvariable

		super().__init__(parent, *args, **kwargs)
		self.parent = parent

	def setText(self,text):
		self.textvariable.set(text)

	def getText(self):
		return self.textvariable.get()

#Entry class that handles its own text variable, and has grayed out default text that disappears upon being focused. Default text is whatever "text" is set to in the constructor
class EntryWithDefaultText(ttk.Entry):
	def __init__(self, parent, *args, **kwargs):
		self.textvariable = tk.StringVar()
		kwargs["textvariable"] = self.textvariable

		if "text" in kwargs:
			self.textvariable.set(kwargs["text"])
			self.defaultText = kwargs["text"]
		else:
			self.defaultText = ""

		self.edited = False

		if "configDictAndKeyToUpdate" in kwargs: #If "configDictAndKeyToUpdate" is provided, the provided config dict will be updated at the provided key to match the entry's current text string whenever the entry's text is modified.
			self.configDictToUpdate = kwargs["configDictAndKeyToUpdate"][0]
			self.configDictKeyToUpdate = kwargs["configDictAndKeyToUpdate"][1]
			self.textvariable.trace("w",self.updateConfigDict)
			del kwargs["configDictAndKeyToUpdate"]

		super().__init__(parent, *args, **kwargs)
		self.parent = parent

		self.s = ttk.Style()
		self.s.configure("grayedOut.TEntry",foreground="gray")
		self["style"] = "grayedOut.TEntry"

		self.bind("<FocusIn>",self.focusIn)
		self.bind("<FocusOut>",self.focusOut)

	def focusIn(self,*args):
		if not self.edited:
			self.edited = True
			self.textvariable.set("")
			self["style"] = "TEntry"

	def focusOut(self,*args):
		if self.getText() == "": #If user focuses out of the entry without entering anything
			self.edited = False #Important that this comes first here; else, updateConfigDict (which is triggered by the next line) will send entry's example text string to self.configDict[self.configDictKey], as opposed to an empty string as it should
			self.textvariable.set(self.defaultText)
			self["style"] = "grayedOut.TEntry"
		else:
			self.edited = True

	def updateConfigDict(self,*args): #Triggered to update the config dict whenever the contents of self.textvariable changes (if a config dict is provided)
		self.configDictToUpdate[self.configDictKeyToUpdate] = self.getText()

	def setText(self,text):
		if text == "":
			self.edited = False
			self["style"] = "grayedOut.TEntry"
			self.textvariable.set(self.defaultText)
		else:
			self.edited = True
			self["style"] = "TEntry"
			self.textvariable.set(text)

	def getText(self):
		if self.edited:
			return self.textvariable.get()
		else:
			return ""

#VMF search button that automatically populates the given Entry field with the path string of the VMF chosen. Don't supply it a command argument, since it handles this internally
class VMFSearchButton(ttk.Button):
	def __init__(self, parent, *args, **kwargs):
		self.entry = kwargs.pop("entry",None)
		kwargs["command"] = self.chooseVMF

		super().__init__(parent, *args, **kwargs)
		self.parent = parent

	def chooseVMF(self, *args):
		if self.entry is not None:
			self.entry.setText(filedialog.askopenfilename(title="Select a VMF",filetypes=[("Valve Map File","*.vmf")]))

#VMF save button that automatically populates the given Entry field with the path string of the VMF being saved. Don't supply it a command argument, since it handles this internally
class VMFSaveButton(ttk.Button):
	def __init__(self, parent, *args, **kwargs):
		self.entry = kwargs.pop("entry",None)
		kwargs["command"] = self.saveVMF

		super().__init__(parent, *args, **kwargs)
		self.parent = parent

	def saveVMF(self, *args):
		if self.entry is not None:
			self.entry.setText(filedialog.asksaveasfilename(title="Save VMF",filetypes=[("Valve Map File","*.vmf")],defaultextension=".vmf"))

app = AutoSky(padding=(8,8,8,8))
app.grid(row=0,column=0)
app.align()
app.mainloop()
