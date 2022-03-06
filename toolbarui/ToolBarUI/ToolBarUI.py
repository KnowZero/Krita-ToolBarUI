from krita import *
import xml.etree.ElementTree as ET
import re
from PyQt5 import uic
import functools
import copy
import json


class ToolBarUI(Extension):
    REACTION_BY = {
        'Default':'default',
        'Left Click':'left',
        'Middle Click':'middle',
        'Right Click':'right',
        'Hover':'hover'
        }
    
    TOOLBAR_TYPE = {
        'Default':'default',
        'Floating Reactive':'float_react',
        'Floating':'float',
        'Floating Reactive Drawer':'float_react_drawer',
        'Floating Drawer':'float_drawer',
        'Docked':'docked'
        }
    
    
    def __init__(self, parent):
        super().__init__(parent)
        self.active = False
        
        settingsData = Krita.instance().readSetting("", "pluginToolBarUI","")
        
        self.settings = {}
        if settingsData.startswith('{'):
            self.settings = json.loads(settingsData)
        else:
        
            self.settings = {
                    'version':0,
                    'count': 0,
                    'config':{},
                    'toolbars':{}
            }
        
        self.toolBars = {}
        self.subActions = {}
        
        self.onConfigReaction = None
        self.reactionState = None
        
        self.itemState = None
        self.toolbarState = None
        
        self.boundActions = []
        
        self.notifier = Krita.instance().notifier()
        self.notifier.windowCreated.connect(self.windowCreatedSetup)

        

    def createActions(self, window):
        self.qwin = window.qwindow()
        

        action = window.createAction("toolbarUI", "ToolBar UI", "tools/scripts")
        
        menu = QMenu("ToolBarUI Menu", self.qwin)
        action.setMenu(menu)
        
        self.subActions['config'] = window.createAction("toolBarUIConfigure", "Configure...", "tools/scripts/toolbarUI")
        #self.subActions['addToolBar'] = window.createAction("toolBarUIAddToolBar", "Add Toolbar...", "tools/scripts/toolbarUI")

        
        self.subActions['config'].triggered.connect( functools.partial(self.writeSettings, self.config ) )
        #self.subActions['addToolBar'].triggered.connect( functools.partial( self.writeSettings, self.configToolBar ) )
        
        
        self.registerToolBars()
        
    def windowCreatedSetup(self):
        self.buildToolBars()

    
    
    def slotEventBroker(self, action):
        self.configItem()
    
    def writeSettings(self, func):

        
        self.tempSettings = copy.deepcopy(self.settings)
        func()
        self.settings = self.tempSettings
        self.settings['version']=0.001
        
        Krita.instance().writeSetting('', 'pluginToolBarUI', json.dumps(self.settings) )
        
        self.registerToolBars()
        self.buildToolBars()

    
    def dialog(self,name, standard = True):
        dlg = QDialog(self.qwin)
        dlg.centralWidget = uic.loadUi(os.path.dirname(os.path.realpath(__file__)) + '/'+name+'.ui')
        layout = QVBoxLayout()
        
        dlg.btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        
        dlg.btns.rejected.connect(dlg.reject)
        
        layout.addWidget(dlg.centralWidget)
        layout.addWidget(dlg.btns)
        dlg.setLayout(layout)
        
        if standard:
            for (k, v) in self.REACTION_BY.items():
                dlg.centralWidget.reactionOpenByCmb.addItem(k, v)
                dlg.centralWidget.reactionCloseByCmb.addItem(k, v)

        
        return dlg
    
    def config(self):
        dlg = self.dialog('ConfigOptions')
        
        

        for (k, v) in self.TOOLBAR_TYPE.items():
            dlg.centralWidget.toolbarTypeCmb.addItem(k, v)

        
        model = QStandardItemModel()
        dlg.centralWidget.toolbarListView.setModel(model)
        
        def fillToolbars():
            model.clear()
            for tuuid in self.tempSettings['toolbars'].keys():
                item = QStandardItem(self.tempSettings['toolbars'][tuuid]['config']['toolbarName'])
                item.setData(tuuid, Qt.UserRole+1)
                model.appendRow(item)
                
        fillToolbars()


        def editToolBar():
            idx = dlg.centralWidget.toolbarListView.selectedIndexes()
            if idx and idx[0]:
                self.configToolBar(idx[0].data(Qt.UserRole+1))
                fillToolbars()

        dlg.centralWidget.toolbarEditBtn.clicked.connect(editToolBar)

        
        def addToolBar():
            self.configToolBar()
            fillToolbars()


        dlg.centralWidget.toolbarAddBtn.clicked.connect(addToolBar)

        def removeToolbar():
            idx = dlg.centralWidget.toolbarListView.selectedIndexes()
            if idx and idx[0]:
                del self.tempSettings['toolbars'][idx[0].data(Qt.UserRole+1)]
                fillToolbars()
        
        dlg.centralWidget.toolbarRemoveBtn.clicked.connect(removeToolbar)

        
        def updateChanges():

            self.saveForm(dlg.centralWidget, self.tempSettings['config'])
            self.settings = self.tempSettings


            dlg.accept()
            
        def cancelChanges():
            
            dlg.reject()
        
        dlg.btns.accepted.connect(updateChanges)
        dlg.btns.rejected.connect(cancelChanges)
        dlg.exec()
        
        #return settings

    def configToolBar(self, tuuid=None):
        dlg = self.dialog('ToolBarOptions')
        
        #settings = self.settings

        
        for (k, v) in self.TOOLBAR_TYPE.items():
            dlg.centralWidget.toolbarTypeCmb.addItem(k, v)
        
        if tuuid is not None: 

            #dlg.centralWidget.toolbarName.setText( self.tempSettings['toolbars'][tuuid]['toolbarName'] )
            self.loadForm(dlg.centralWidget,self.tempSettings['toolbars'][tuuid]['config'])
            self.toolbarState = copy.deepcopy(self.tempSettings['toolbars'][tuuid])
        else:
            tuuid = QUuid.createUuid().toString()
            self.tempSettings['toolbars'][tuuid]={
                'config':{
                    'toolbarName': "ToolBar "+tuuid
                    },
                'top':{
                    'items':[]
                    },
                'bottom':{
                    'items':[]
                    }
                }
            dlg.centralWidget.toolbarName.setText( "ToolBar "+tuuid )
            self.toolbarState = None

            
            #toolbar = ToolBarUIPanel(self.qwin)
        
        topModel = QStandardItemModel()
        dlg.centralWidget.topbarListView.setModel(topModel)
        bottomModel = QStandardItemModel()
        dlg.centralWidget.bottombarListView.setModel(bottomModel)

        def fillItems():
            topModel.clear()
            for (i, v) in enumerate(self.tempSettings['toolbars'][tuuid]['top']['items']):
                item = QStandardItem(v['alias'])
                item.setData(v['uuid'], Qt.UserRole+1)
                topModel.appendRow(item)

            bottomModel.clear()
            for (i, v) in enumerate(self.tempSettings['toolbars'][tuuid]['bottom']['items']):
                item = QStandardItem(v['alias'])
                item.setData(v['uuid'], Qt.UserRole+1)
                bottomModel.appendRow(item)
                
        fillItems()


        def editItem(subpanel):
            currentPanel = getattr( dlg.centralWidget, subpanel+'barListView' )
            idx = currentPanel.selectedIndexes()
            if idx and idx[0]:
                self.configItem(tuuid,subpanel,idx[0].row())
                fillItems()

        
        def addItem(subpanel):
            self.configItem(tuuid,subpanel)
            fillItems()
            
        def removeItem(subpanel):
            currentPanel = getattr( dlg.centralWidget, subpanel+'barListView' )
            idx = currentPanel.selectedIndexes()
            if idx and idx[0]:
                self.tempSettings['toolbars'][tuuid]['top']['items'].pop( idx[0].row() )
                fillItems()
            
        dlg.centralWidget.topbarAddBtn.clicked.connect( functools.partial(addItem,'top') )
        dlg.centralWidget.bottombarAddBtn.clicked.connect( functools.partial(addItem,'bottom') )
        
        dlg.centralWidget.topbarRemoveBtn.clicked.connect( functools.partial(removeItem,'top') )
        dlg.centralWidget.bottombarRemoveBtn.clicked.connect( functools.partial(removeItem,'bottom') )
        
        dlg.centralWidget.topbarEditBtn.clicked.connect( functools.partial(editItem,'top') )
        dlg.centralWidget.bottombarEditBtn.clicked.connect( functools.partial(editItem,'bottom') )
        
        def updateChanges():
            #self.tempSettings['toolbars'][tuuid]['config']['toolbarName']=dlg.centralWidget.toolbarName.text()
            self.saveForm(dlg.centralWidget, self.tempSettings['toolbars'][tuuid]['config'])
            dlg.accept()
        
        def cancelChanges():
            if self.toolbarState is None:
                del self.tempSettings['toolbars'][tuuid]
            else:
                self.tempSettings['toolbars'][tuuid]=self.toolbarState
            dlg.reject()
        
        dlg.btns.accepted.connect(updateChanges)
        dlg.btns.rejected.connect(cancelChanges)
        dlg.exec()

        #if 'toolbarName' not in self.tempSettings['toolbars'][tuuid]['config']: 
        #    del self.tempSettings['toolbars'][tuuid]
        #return settings
    
    def configItem(self,tuuid,subpanel, irow = None):
        dlg = self.dialog('ItemOptions')
        
        self.onConfigReaction = 0
        
        for (k, v) in self.tempSettings['toolbars'].items():
            dlg.centralWidget.toolbarCmb.addItem(v['config']['toolbarName'], v)


        if irow is None: 
            iuuid = QUuid.createUuid().toString()
            self.tempSettings['toolbars'][tuuid][subpanel]['items'].append({
                'uuid': iuuid,
                'alias': 'Item '+iuuid,
                'reactions':[{
                    'alias':'First',
                    'uuid': QUuid.createUuid().toString(),
                    'actions':[],
                    'dockers':[],
                    'config':{}
                    }]
                })
            irow = len(self.tempSettings['toolbars'][tuuid][subpanel]['items'])-1
            self.itemState = None
        else:
            self.itemState = copy.deepcopy(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow])


        
        model = QStandardItemModel()
        dlg.centralWidget.reactionListView.setModel(model)


        actionModel = QStandardItemModel()
        dlg.centralWidget.actionsListView.setModel(actionModel)



        def fillReactions(select = 0):
            model.clear()
            for (i,v) in enumerate(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions']):
                item = QStandardItem(v['alias'])
                item.setData(tuuid, Qt.UserRole+1)
                model.appendRow(item)
                if i == select: dlg.centralWidget.reactionListView.selectionModel().select( model.indexFromItem(item), QItemSelectionModel.Select )
        
        

        
        def updateReactionChanges():
            srow = self.onConfigReaction

            self.saveForm(dlg.centralWidget.reactionGroup, self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['config'])
            
            rec = self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]
            self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['alias'] = 'Reaction '+self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['uuid']
            
            if rec['config']['reactionTypeCmb'] == 'Action Collection':
                if len(rec['actions']) > 1:
                    self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['alias'] = rec['config']['reactionOpenByCmb'] + ' - Action List['+str(len(rec['actions']))+']: ' + rec['actions'][0]['name']
                elif len(rec['actions']) == 1:
                    self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['alias'] = rec['config']['reactionOpenByCmb'] + ' - Action: ' + rec['actions'][0]['name']

            
            if len(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions']) > 0 and len(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][0]['actions']) > 0:
                self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['alias']=self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][0]['actions'][0]['name']
            #self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['config']['reactionCloseByCmb']='hover'
            #print ( "SAVE" , srow, self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'] )
            fillReactions(srow)
        
        def addReaction():
            self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][self.onConfigReaction]=self.reactionState
            
            self.configReaction(dlg, tuuid, subpanel, irow)

            fillReactions( len(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'])-1 )
            
        def editReaction(sel,desl):
            srow = sel.indexes()[0].row()
            
            if desl:
                self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][self.onConfigReaction]=self.reactionState

           
            self.configReaction(dlg, tuuid, subpanel, irow,  srow)
            fillActions()
            #fillReactions()
        




        
        dlg.centralWidget.reactionTypeCmb.currentIndexChanged.connect(dlg.centralWidget.stackedWidget.setCurrentIndex)
        dlg.centralWidget.reactionUpdateBtn.clicked.connect(updateReactionChanges)
        

        dlg.centralWidget.reactionAddBtn.clicked.connect( addReaction )
        dlg.centralWidget.reactionListView.selectionModel().selectionChanged.connect( editReaction )
        

        def fillActions(select = 0):
            srow = self.onConfigReaction
            actionModel.clear()
            for (i,v) in enumerate(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['actions']):
                item = QStandardItem(Krita.instance().icon(v['icon']),v['name']) if v['icon'] != '' else QStandardItem(v['name'])
                item.setData(v['name'], Qt.UserRole+1)
                actionModel.appendRow(item)
                if i == select: dlg.centralWidget.actionsListView.selectionModel().select( actionModel.indexFromItem(item), QItemSelectionModel.Select )
        
        def addAction():
            srow = self.onConfigReaction
            action = self.getAction()
            
            self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['actions'].append({
                'name': action[0],
                'icon': '' if action[1].startswith('[') else action[1]
                })
            
            fillActions(len(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['actions'])-1)
            
        def removeAction():
            srow = self.onConfigReaction
            idx = dlg.centralWidget.actionsListView.selectionModel().selectedIndexes()
            if idx and idx[0]:
                self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['actions'].pop(idx[0].row())
            fillActions(idx[0].row()-1)
            
        def upAction():
            srow = self.onConfigReaction
            idx = dlg.centralWidget.actionsListView.selectionModel().selectedIndexes()
            if idx and idx[0]:
                
                fillActions(self.swapOrder(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['actions'],idx[0].row(),-1))
                
        def downAction():
            srow = self.onConfigReaction
            idx = dlg.centralWidget.actionsListView.selectionModel().selectedIndexes()
            if idx and idx[0]:
                
                fillActions(self.swapOrder(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['actions'],idx[0].row(),1))
            

        dlg.centralWidget.actionAddBtn.clicked.connect(addAction)
        dlg.centralWidget.actionRemoveBtn.clicked.connect(removeAction)
        dlg.centralWidget.actionOrderUpBtn.clicked.connect(upAction)
        dlg.centralWidget.actionOrderDownBtn.clicked.connect(downAction)
        
        fillReactions()

        def updateChanges():
            self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][self.onConfigReaction]=self.reactionState
            #self.saveForm(dlg.centralWidget, self.tempSettings['toolbars'][tuuid]['config'])
            dlg.accept()
        
        def cancelChanges():
            if self.itemState is None:
                self.tempSettings['toolbars'][tuuid][subpanel]['items'].pop(irow)
            else:
                self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow] = self.itemState
            dlg.reject()
        
        dlg.btns.accepted.connect(updateChanges)
        dlg.btns.rejected.connect(cancelChanges)
        dlg.exec()
        
        
    def configReaction(self, dlg, tuuid, subpanel, irow, srow = None):

        if srow is not None: 
            #print ("LOAD", self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'] )
            self.loadForm(dlg.centralWidget,self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow]['config'])
            
        else:
            ruuid = QUuid.createUuid().toString()
            self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'].append({
                'uuid': ruuid,
                'alias': 'Reaction '+ruuid,
                'actions':[],
                'dockers':[],
                'config':{}
                })
            srow = len(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'])-1
        
        self.onConfigReaction = srow
        self.reactionState = copy.deepcopy(self.tempSettings['toolbars'][tuuid][subpanel]['items'][irow]['reactions'][srow])


            

        #dlg.centralWidget.reactionUpdateBtn.clicked.disconnect()

    def getAction(self, action = None):
        dlg = self.dialog('ActionPicker', False)
        
        tableView = dlg.centralWidget.actionsTableView
            
        tableModel = QStandardItemModel()
        proxyModel = QSortFilterProxyModel()
        tableModel.setHorizontalHeaderLabels(['Name', 'Description'])

        proxyModel.setSourceModel(tableModel)
        tableView.setModel(proxyModel)
            
        proxyModel.setFilterCaseSensitivity( Qt.CaseInsensitive )
        proxyModel.setFilterKeyColumn(-1)
            
        parentItem = tableModel.invisibleRootItem()
                
        for action in  Krita.instance().actions():
            parentItem.appendRow([
                QStandardItem( action.objectName() ), 
                QStandardItem( action.icon(), action.toolTip() )
            ])

        dlg.centralWidget.actionsFilter.textChanged.connect(proxyModel.setFilterFixedString)
        

        
        def iconPicker():
            dlg.centralWidget.iconLabel.setText( self.getIcon() )
            
        def iconClear():
            dlg.centralWidget.iconLabel.setText( '[Default Icon]' )
        
        dlg.centralWidget.iconPickBtn.clicked.connect(iconPicker)
        dlg.centralWidget.iconClearBtn.clicked.connect(iconClear)
        
        def updateChanges():
            dlg.accept()
        
        dlg.btns.accepted.connect(updateChanges)
        dlg.exec()
        return [tableView.selectionModel().selectedRows()[0].data(0), dlg.centralWidget.iconLabel.text()]
        
    def getIcon(self, icon = None):
        dlg = self.dialog('IconPicker', False)
        
       
        listView = dlg.centralWidget.iconsListView
        
        listView.setGridSize( QSize(128,128) )
        
        listModel = QStandardItemModel()
        proxyModel = QSortFilterProxyModel()

        proxyModel.setSourceModel(listModel)
        listView.setModel(proxyModel)
        
        proxyModel.setFilterCaseSensitivity( Qt.CaseInsensitive )
        

        def loadIconList():
            iconDict = {}
            
            listModel.clear()
            
            iconFormats = ["*.svg","*.svgz","*.svz","*.png"]
            
            if dlg.centralWidget.boolIconsKrita.isChecked():
                iconList = QDir(":/pics/").entryList(iconFormats, QDir.Files)
                iconList += QDir(":/").entryList(iconFormats, QDir.Files)
                
                for iconName in iconList:
                    name = iconName.split('_',1)
                    if any(iconSize == name[0] for iconSize in [ '16', '22', '24', '32', '48', '64', '128', '256', '512', '1048' ]):
                        iconName = name[1]
                        
                    name = iconName.split('_',1)
                    if any(iconSize == name[0] for iconSize in [ 'light', 'dark' ]):
                        iconName = name[1]
                        
                    name = iconName.split('.')
                    iconName = name[0]
                    iconDict[iconName]={}
                
            if dlg.centralWidget.boolIconsKritaExtra.isChecked():
                iconList = QDir(":/icons/").entryList(iconFormats, QDir.Files)
                #iconList += QDir(":/images/").entryList(iconFormats, QDir.Files)

                for iconName in iconList:
                    name = iconName.split('.')
                    iconName = name[0]
                    iconDict[iconName]={}


            if dlg.centralWidget.boolIconsTheme.isChecked():
                with open( os.path.dirname(os.path.realpath(__file__)) + '/ThemeIcons.txt' ) as f:
                    for iconName in f.readlines():
                        iconDict[iconName.rstrip()]={}

            
            for iconName, iconInfo in sorted(iconDict.items()):
                    item = QStandardItem( Krita.instance().icon(iconName), iconName )
                    
                    listModel.appendRow( item )


        loadIconList()

        iconsGroup = QButtonGroup(dlg.centralWidget)
        iconsGroup.setExclusive(False)
        
        iconsGroup.addButton( dlg.centralWidget.boolIconsKrita )
        iconsGroup.addButton( dlg.centralWidget.boolIconsKritaExtra )
        iconsGroup.addButton( dlg.centralWidget.boolIconsTheme )

        iconsGroup.buttonToggled.connect(loadIconList)
        dlg.centralWidget.iconsFilter.textChanged.connect(proxyModel.setFilterFixedString)
    
    
        def updateChanges():
            dlg.accept()
        
        dlg.btns.accepted.connect(updateChanges)
        dlg.exec()
        
        return listView.selectionModel().selectedIndexes()[0].data(0)
    
    def swapOrder(self, item, row, i):
        if i == -1 and row > 0:
            item[row-1], item[row] = item[row], item[row-1]
            return row-1
        elif i == 1 and row < len(item)-1:
            item[row], item[row+1] = item[row+1], item[row]
            return row+1
        return row

    
    def loadForm(self, form, items):
        for (k, v) in items.items():
            w = getattr(form,k)
            if isinstance(w,QLineEdit):
                w.setText(v)
            elif isinstance(w,QSpinBox):
                w.setValue(v)
            elif isinstance(w,QComboBox):
                if w.currentData():
                    w.setCurrentIndex(w.findData(v))
                else:
                    w.setCurrentIndex(w.findText(v))

    def saveForm(self, form, items):
        for w in form.findChildren(QWidget):
            if '_' not in w.objectName():
                if isinstance(w,QLineEdit):
                    items[w.objectName()]=w.text()
                elif isinstance(w,QSpinBox):
                    items[w.objectName()]=w.value()
                elif isinstance(w,QComboBox):
                    if w.currentData():
                        items[w.objectName()]=w.currentData()
                    else:
                        items[w.objectName()]=w.currentText()
                

    def registerToolBars(self):
        toolbars={}
        tmap = {}
        
        for sig in self.boundActions:
            QObject.disconnect(sig)
        
        for tuuid in self.settings['toolbars'].keys():
            tmap[self.settings['toolbars'][tuuid]['config']['toolbarName']]=tuuid

        for w in self.qwin.children(): 
            if isinstance(w,QToolBar):
                name = w.objectName()
                if name.startswith('ToolBarUI: '):
                    name = name.split('ToolBarUI: ')[1]
                    toolbars[tmap[name]]=w
        
        for tuuid in self.settings['toolbars'].keys():
            if tuuid not in toolbars.keys():
                toolbar = ToolBarUIPanel('ToolBarUI: '+self.settings['toolbars'][tuuid]['config']['toolbarName'], tuuid, self, self.qwin)
            
                self.qwin.addToolBar(toolbar)
                self.toolBars[tuuid]=toolbar
    
    
    def buildToolBars(self):
        for tuuid in self.settings['toolbars'].keys():
            self.toolBars[tuuid].clear()
            self.buildItems(tuuid)
            
    def buildItems(self, tuuid):
        t = self.toolBars[tuuid]
        s = self.settings['toolbars'][tuuid]
        
        for panel in ('top','bottom'):
            for i, iv in enumerate(s[panel]['items']):
                t.addItem(panel, iv)

            
            
            
            
    
    def setup(self):
        pass


class ToolBarUIPanel(QToolBar):
    def __init__(self, name, uuid, caller, parent=None):
        super().__init__()
        self.caller = caller
        self.setObjectName(name)
        self.uuid = uuid
        self.items = { 
            'top':[],
            'bottom':[]
            }
        
    def addItem(self, panel, item):
        self.items[panel].append(ToolBarUIButton(item, self))
        self.addWidget(self.items[panel][-1])


        

class ToolBarUIButton(QToolButton):
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.toolbar = parent
        self.s = item
        self.popup = None
        
        if item['reactions'][0]['config']['reactionTypeCmb'] == 'Action Collection':
            ra = item['reactions'][0]['actions'][0]
            action = Krita.instance().action(ra['name'])
            
            self.setIcon(action.icon() if ra['icon'] == '' else Krita.instance().icon(ra['icon']))
            self.setToolTip(action.toolTip())
            
            if action.isCheckable():
                self.setCheckable(True)
                if action.isChecked(): self.actionChanged(action, True)
                self.toolbar.caller.boundActions.append( action.toggled.connect( functools.partial( self.actionChanged, action )  ) )
            

    def actionChanged(self, action, status):
        self.setChecked(status)
    
    def enterEvent(self, event):
        for (i,r) in enumerate(self.s['reactions']):
            if r['config']['reactionOpenByCmb'] == 'hover':
                self.openItem(r)
    
    def mousePressEvent(self, event):
        for (i,r) in enumerate(self.s['reactions']):
            if event.buttons() == Qt.LeftButton and r['config']['reactionOpenByCmb'] == 'left':
                self.openItem(r)
            if event.buttons() == Qt.MiddleButton and r['config']['reactionOpenByCmb'] == 'middle':
                self.openItem(r)
            elif event.buttons() == Qt.RightButton and r['config']['reactionOpenByCmb'] == 'right':
                self.openItem(r)
                
    def openItem(self, r):
        if r['config']['reactionTypeCmb'] == 'Action Collection':
            if len(r['actions']) == 1:
                Krita.instance().action( r['actions'][0]['name'] ).trigger()
            else:
                self.popup = QWidget()
                grid = QGridLayout
                self.popup.setLayout(grid)
                print ("SHOW ACTIONS!")




app = Krita.instance()
extension = ToolBarUI(parent=app)
app.addExtension(extension)


    
