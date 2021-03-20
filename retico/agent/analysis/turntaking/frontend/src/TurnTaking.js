import React, { Component, useState } from "react";
import { Navbar, Nav, NavDropdown, Tab, Tabs } from 'react-bootstrap';

import Dialog from './Dialog'
import Annotation from './Annotation'
import ChatAgent from './ChatAgent'
import Global from './Global';

import './App.css';
import 'bootstrap/dist/css/bootstrap.min.css';


// const paramsURL = "/api/file/hparams";


const Navigation = (props) => {
  const [key, setKey] = useState('dialog');

  // fetch(paramsURL).then(response => response.json()).then((data) => {
  //   setParams({params: data})
  // })
  // console.log('params: ', params)

  const interactions = ['session_0/baseline', 'session_0/prediction', 'session_0/baselinevad']

  const items = interactions.map((s, i) => { 
    return <NavDropdown.Item href="/" key={i}> {s} </NavDropdown.Item> 
  })

  return (
    <Navbar expand="sm"> 
      <Navbar.Collapse id="basic-navbar-nav">
        <Tabs 
          activeKey={key}
          onSelect={(k) => {
            props.onChangeContent(k); 
            setKey(k)
          }}
          className="mr-auto"
        >
          <Tab eventKey='dialog' title="Dialog" /> 
          <Tab eventKey='global' title="Global" /> 
          <Tab eventKey='annotation' title="Annotation" /> 
          <Tab eventKey='chatagent' title="Chat" /> 
        </Tabs >
        <Nav className="justify-content-end">
          <NavDropdown title="Interactions" id="basic-nav-dropdown" menuRole="right">
            {items}
          </NavDropdown>
        </Nav>
      </Navbar.Collapse>
    </Navbar>
  );
};


export default class TurnTaking extends Component {
  constructor(props) {
    super(props);
    this.state = { 
      content: 'dialog',
      interaction: 'session_1/prediction',
      Dialog: null,
      Global: null,
      Annotation: null,
      ChatAgent: null,
    };
    this.onChangeContent=this.onChangeContent.bind(this)
  }

  componentDidMount() {
    this.setState({Dialog:  <Dialog interaction={this.state.interaction}/>})
  }


  onChangeContent(content) {
    this.setState({content: content});
  }

  getContent() {
    let content;
    if (this.state.content === 'global'){
      content = <Global interaction={this.state.interaction}/>
    } else if (this.state.content === 'annotation') {
      content = <Annotation />
    } else if (this.state.content === 'chatagent') {
      content = <Annotation />
    } else {
      content = this.state.Dialog;
    }
    return content
  }

  render () {
    const content = this.getContent();
    return (
      <div>
        <Navigation onChangeContent={this.onChangeContent} />
        <h4>{this.state.interaction}</h4>
        {content}
      </div>
    );
  }
}
