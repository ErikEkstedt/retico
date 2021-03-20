import React, { Component } from "react";
import WaveSurfer from "wavesurfer.js";


export default class Audio extends Component {
  constructor(props) {
    super(props);
    this.state = {
      playPauseButtonId: 'pause',
      color: "#fafafa",
    };
  }

  // Waveform + AudioPlayer
  componentDidMount() {
    this.waveform = WaveSurfer.create({
      container: '#'+this.props.id,
      backend: "MediaElement",
      mediaControls: true,
      backgroundColor: this.state.color,
      // progressColor: this.props.progressColor,
      scrollParent: true,
    });
    this.waveform.load(this.props.audioURL);
  }

  render() {
    return (
      <div id={this.props.id}></div>
    );
  }
}
