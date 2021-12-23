const {
    app,
    BrowserWindow,
    ipcMain
} = require('electron')
const path = require('path')
const fs = require('fs')

app.setName("FreeDATA");

var appDataFolder = process.env.APPDATA || (process.platform == 'darwin' ? process.env.HOME + '/Library/Application Support' : process.env.HOME + "/.config")
var configFolder = path.join(appDataFolder, "FreeDATA");
var configPath = path.join(configFolder, 'config.json')

// create config folder if not exists
if (!fs.existsSync(configFolder)) {
    fs.mkdirSync(configFolder);
}

// create config file if not exists
var configContent = `
{
  "tnc_host": "192.168.178.163",
  "tnc_port": "3000",
  "daemon_host": "192.168.178.163",
  "daemon_port": "3001",
  "mycall": "AA0AA",
  "mygrid": "JN40aa",
  "deviceid": "2028",
  "deviceport": "/dev/ttyUSB0",
  "serialspeed": "9600",
  "ptt": "RTS",
  "spectrum": "scatter",
  "tnclocation": "localhost"
}
`;
if (!fs.existsSync(configPath)) {
    fs.writeFileSync(configPath, configContent)
}



var chatDB = path.join(configFolder, 'chatDB.json')
// create chat database file if not exists
var configContent = `
{ "chatDB" : [{
    "id" : "00000000",
    "timestamp" : 1234566,
    "mycall" : "AA0AA",
    "dxcall" : "AB0AB",
    "dxgrid" : "JN1200",
    "message" : "hallowelt"
}]
}
`;
if (!fs.existsSync(chatDB)) {
    fs.writeFileSync(chatDB, configContent)
}



/*
// Creates receivedFiles folder if not exists
// https://stackoverflow.com/a/26227660
var appDataFolder = process.env.HOME
var applicationFolder = path.join(appDataFolder, "FreeDATA");
var receivedFilesFolder = path.join(applicationFolder, "receivedFiles");

// https://stackoverflow.com/a/13544465
fs.mkdir(receivedFilesFolder, {
    recursive: true
}, function(err) {
    console.log(err);
});

*/



const config = require(configPath);
const exec = require('child_process').exec;

let win = null;
let data = null;
var daemonProcess = null;

function createWindow() {
    win = new BrowserWindow({
        width: 1000,
        height: 430,
        autoHideMenuBar: true,
        icon: __dirname + '/src/app-icon.png',
        webPreferences: {
            //preload: path.join(__dirname, 'preload-main.js'),
            preload: require.resolve('./preload-main.js'),
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: false, //https://stackoverflow.com/questions/53390798/opening-new-window-electron/53393655 https://github.com/electron/remote
        }
    })
    // hide menu bar
    win.setMenuBarVisibility(false)

    //open dev tools
    /*win.webContents.openDevTools({
        mode: 'undocked',
        activate: true,
    })
    */
    win.loadFile('src/index.html')
    
    chat = new BrowserWindow({
        height: 900,
        width: 600,
        show: false,
        parent: win,
        webPreferences: {
            preload: require.resolve('./preload-chat.js'),
            nodeIntegration: true,

        }
    })

    chat.loadFile('src/chat-module.html')
    chat.setMenuBarVisibility(false)


    // Emitted when the window is closed.
    win.on('closed', function() {
        // Dereference the window object, usually you would store windows
        // in an array if your app supports multi windows, this is the time
        // when you should delete the corresponding element.
        win = null;
        chat = null;
    })

    
    chat.on('closed', function () {
            // Dereference the window object, usually you would store windows
            // in an array if your app supports multi windows, this is the time
            // when you should delete the corresponding element.
        })
    

    // https://stackoverflow.com/questions/44258831/only-hide-the-window-when-closing-it-electron
    chat.on('close', function(evt) {
        evt.preventDefault();
        chat.hide()
    });
    
}

app.whenReady().then(() => {
    createWindow()

    // start daemon
    // https://stackoverflow.com/a/5775120
    console.log("Trying to start daemon binary")
    daemonProcess = exec('./daemon', function callback(err, stdout, stderr) {
        if (err) {
            console.error("Can't start daemon binary");
            console.error("--> this is only working with the app bundle and a precompiled binaries");
        return;
        }
        console.log(stdout); 
    });





    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow()
        }
    })
})

app.on('window-all-closed', () => {
    // kill daemon process
    daemonProcess.kill('SIGINT');

    if (process.platform !== 'darwin') {
        app.quit()
    }
})

// IPC HANDLER

ipcMain.on('request-show-chat-window', (event, arg) => {
    chat.show()
 });


ipcMain.on('request-update-tnc-state', (event, arg) => {
    win.webContents.send('action-update-tnc-state', arg);
    //data.webContents.send('action-update-tnc-state', arg);
});

/*
ipcMain.on('request-update-data-state', (event, arg) => {
    //win.webContents.send('action-update-data-state', arg);
    //data.webContents.send('action-update-data-state', arg);
});

ipcMain.on('request-update-heard-stations', (event, arg) => {
    win.webContents.send('action-update-heard-stations', arg);
});
*/
ipcMain.on('request-update-daemon-state', (event, arg) => {
    win.webContents.send('action-update-daemon-state', arg);
});

ipcMain.on('request-update-hamlib-test', (event, arg) => {
    win.webContents.send('action-update-hamlib-test', arg);
});




ipcMain.on('request-update-daemon-connection', (event, arg) => {
    win.webContents.send('action-update-daemon-connection', arg);
});

ipcMain.on('run-tnc-command', (event, arg) => {
    win.webContents.send('run-tnc-command', arg);
});

ipcMain.on('request-update-rx-buffer', (event, arg) => {
    win.webContents.send('action-update-rx-buffer', arg);
});

ipcMain.on('request-update-rx-msg-buffer', (event, arg) => {
    chat.webContents.send('action-update-rx-msg-buffer', arg);
});
