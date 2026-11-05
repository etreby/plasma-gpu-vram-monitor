import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.plasma.components 3.0 as PC
import org.kde.plasma.plasmoid 2.0

Item {
    id: root
    property var cards: []
    property bool healthy: false
    property string problem: "Loading GPU sensors…"
    property double lastUpdate: 0
    readonly property string command: "python3 " + shellQuote(decodeURIComponent(Qt.resolvedUrl("../scripts/gpu-panel-data.py").toString().replace(/^file:\/\//, "")))
    function shellQuote(value) { return "'" + value.replace(/'/g, "'\\''") + "'" }
    function temp(v) { return v === null || v === undefined ? "—" : Math.round(v) + "°" }
    function percent(v) { return v === null || v === undefined ? "—" : Math.round(v) + "%" }
    function memory(c) { return c.used === null || !c.total ? "—" : (c.used/1024).toFixed(1) + "/" + Math.round(c.total/1024) + " GiB" }
    function heat(v) { return v >= 95 ? PlasmaCore.Theme.negativeTextColor : v >= 80 ? PlasmaCore.Theme.neutralTextColor : PlasmaCore.Theme.textColor }
    function details() {
        if (!healthy) return problem
        return cards.map(function(c) { return c.name + "\nCore: " + temp(c.core) + "C · Hotspot: " + temp(c.junction) + "C · VRAM: " + temp(c.vram) + "C\nGPU load: " + percent(c.load) + " · Memory activity: " + percent(c.memoryLoad) + "\nVRAM used: " + memory(c) }).join("\n\n") + "\n\nUpdates every 3 seconds. Temperatures: core / VRAM."
    }
    Plasmoid.preferredRepresentation: Plasmoid.compactRepresentation
    Plasmoid.toolTipMainText: "GPU & VRAM Monitor"
    Plasmoid.toolTipSubText: details()
    Plasmoid.compactRepresentation: Item {
        Layout.minimumWidth: units.gridUnit * 25
        Layout.preferredWidth: units.gridUnit * 25
        Layout.maximumWidth: units.gridUnit * 25
        Layout.fillHeight: true
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: units.smallSpacing
            anchors.rightMargin: units.smallSpacing
            spacing: units.largeSpacing
            Repeater {
                model: root.cards
                delegate: ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        PC.Label { text: modelData.name; font.bold: true; font.pixelSize: units.gridUnit * 0.63 }
                        Item { Layout.fillWidth: true }
                        PC.Label { text: "C " + root.temp(modelData.core); font.pixelSize: units.gridUnit * 0.63; color: root.healthy ? root.heat(modelData.core) : PlasmaCore.Theme.disabledTextColor }
                        PC.Label { text: "M " + root.temp(modelData.vram); font.pixelSize: units.gridUnit * 0.63; color: root.healthy ? root.heat(modelData.vram) : PlasmaCore.Theme.disabledTextColor }
                    }
                    PC.Label {
                        text: root.healthy ? root.percent(modelData.load) + " GPU  ·  " + root.memory(modelData) : "Sensors unavailable"
                        font.pixelSize: units.gridUnit * 0.56
                        color: root.healthy ? PlasmaCore.Theme.textColor : PlasmaCore.Theme.disabledTextColor
                        opacity: 0.85
                    }
                }
            }
            PC.Label { visible: root.cards.length === 0; text: root.problem; elide: Text.ElideRight; Layout.fillWidth: true }
        }
    }
    Plasmoid.fullRepresentation: Item {
        Layout.minimumWidth: units.gridUnit * 28
        Layout.minimumHeight: units.gridUnit * 15
        PC.Label { anchors.fill: parent; anchors.margins: units.largeSpacing; text: root.details(); wrapMode: Text.WordWrap }
    }
    PlasmaCore.DataSource {
        id: process
        engine: "executable"
        connectedSources: []
        onNewData: {
            disconnectSource(sourceName)
            try {
                var sample = JSON.parse(data.stdout)
                if (sample.ok) { root.cards = sample.cards; root.healthy = true; root.lastUpdate = Date.now() }
                else { root.healthy = false; root.problem = sample.error }
            } catch (e) { root.healthy = false; root.problem = "GPU sensors unavailable" }
        }
    }
    Timer {
        interval: 3000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            if (root.lastUpdate && Date.now() - root.lastUpdate > 15000) { root.healthy = false; root.problem = "GPU readings are stale" }
            if (process.connectedSources.length === 0) process.connectSource(root.command)
        }
    }
}
